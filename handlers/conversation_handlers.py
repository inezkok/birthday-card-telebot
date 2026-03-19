"""
Multi-step conversation flow commands
======================================
Flows
-----
/write      : pick birthday person → type wish → confirm
/collate    : pick birthday person → generate card → send to admin
/admin      : pick user → pick new role → confirm
/adduser    : enter handle → name → birthday → role → confirm
/removeuser : pick user → confirm

Important: all keyboard callback data uses users.id (the surrogate key),
not telegram_id.  This is safe for both active and pending users.
"""

from datetime import date
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

import database as db
from utils.date_utils import next_month_str
from utils.auth import registered_only, admin_only
from utils.card_generator import generate_card

# -------------------- STATE CONSTANTS --------------------

# /write
WRITE_SELECT_PERSON, WRITE_TYPE_MESSAGE, WRITE_CONFIRM = range(3)

# /collate
COLLATE_SELECT_PERSON = range(3, 4)

# /admin
ADMIN_SELECT_USER, ADMIN_SELECT_ROLE = range(4, 6)

# /adduser
ADD_HANDLE, ADD_NAME, ADD_BIRTHDAY, ADD_ROLE, ADD_CONFIRM = range(6, 11)

# /removeuser
REMOVE_SELECT_USER, REMOVE_CONFIRM = range(11, 13)

# State maps consumed by ConversationHandler in bot.py
WRITE_STATES    = {WRITE_SELECT_PERSON: [], WRITE_TYPE_MESSAGE: [], WRITE_CONFIRM: []}
COLLATE_STATES  = {COLLATE_SELECT_PERSON[0]: []}
ADMIN_STATES    = {ADMIN_SELECT_USER: [], ADMIN_SELECT_ROLE: []}
ADDUSER_STATES  = {ADD_HANDLE: [], ADD_NAME: [], ADD_BIRTHDAY: [],
                   ADD_ROLE: [], ADD_CONFIRM: []}
REMOVEUSER_STATES = {REMOVE_SELECT_USER: [], REMOVE_CONFIRM: []}

# -------------------- SHARED HELPERS --------------------

def _escape_markdown(text: str) -> str:
    """Escape Markdown special characters to prevent parsing errors."""
    special_chars = ['*', '_', '`', '[']
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    return text

def _bday_baby_keyboard(babies: list, prefix: str) -> InlineKeyboardMarkup:
    """Keyboard of active birthday people. Callback data uses users.id."""
    buttons = [
        [InlineKeyboardButton(f"🎂 {b['name']}", callback_data=f"{prefix}:{b['id']}")]
        for b in babies
    ]
    buttons.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel")])
    return InlineKeyboardMarkup(buttons)

def _user_keyboard(users: list, prefix: str) -> InlineKeyboardMarkup:
    """
    Keyboard of users.  Callback data uses users.id.
    Pending users are labelled so admins can identify them.
    """
    buttons = []
    for u in users:
        label = f"👤 {u['name']}"
        if u["pending"]:
            label += " ⏳ (pending)"
        buttons.append([InlineKeyboardButton(label, callback_data=f"{prefix}:{u['id']}")])
    buttons.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel")])
    return InlineKeyboardMarkup(buttons)

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text("Operation cancelled. ✋")
    else:
        await update.message.reply_text("Operation cancelled. ✋")
    return ConversationHandler.END

async def handle_stray_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Catch any callback that falls outside an active conversation."""
    await update.callback_query.answer("This menu has expired. Please use a command again.")


# -------------------- /WRITE FLOW --------------------

@registered_only
async def write_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    tg_id     = update.effective_user.id
    me        = db.get_user_by_telegram_id(tg_id)
    month_num = (date.today().month % 12) + 1
    target    = next_month_str()

    # Only active users, excluding the writer themselves
    babies = [b for b in db.get_birthdays_in_month(month_num)
              if b["id"] != me["id"]]

    if not babies:
        await update.message.reply_text(
            "No one (other than yourself) has a birthday next month. Check back later! 🗓️"
        )
        return ConversationHandler.END

    context.user_data["write_target_month"] = target
    context.user_data["write_my_id"] = me["id"]
    await update.message.reply_text(
        f"🎂 *Write a Birthday Wish*\n\nWho would you like to write a wish for? "
        f"(Birthdays in {target})",
        parse_mode="Markdown",
        reply_markup=_bday_baby_keyboard(babies, "write_person"),
    )
    return WRITE_SELECT_PERSON

async def write_person_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    person_id = int(query.data.split(":", 1)[1])

    person = db.get_user_by_id(person_id)
    if not person:
        await query.edit_message_text("User not found. Please try again with /write.")
        return ConversationHandler.END

    context.user_data["write_person_id"]   = person_id
    context.user_data["write_person_name"] = person["name"]

    target   = context.user_data["write_target_month"]
    my_id    = context.user_data["write_my_id"]
    existing = db.get_wish(my_id, person_id, target)
    hint     = (f'\n\n_Your current wish:_\n"{existing["message"]}"' if existing else "")

    await query.edit_message_text(
        f"✏️ Write your birthday message for *{person['name']}*.\n"
        f"Send it as a plain text message.{hint}\n\n"
        "_Tip: Type /cancel to abort._",
        parse_mode="Markdown",
    )
    return WRITE_TYPE_MESSAGE

async def write_message_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    message = update.message.text.strip()
    if not message:
        await update.message.reply_text("Please send a non-empty message!")
        return WRITE_TYPE_MESSAGE

    context.user_data["write_message"] = message
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Confirm", callback_data="write_confirm"),
         InlineKeyboardButton("✏️ Edit",    callback_data="write_edit")],
        [InlineKeyboardButton("❌ Cancel",  callback_data="cancel")],
    ])
    await update.message.reply_text(
        f"📝 *Preview* — wish for *{_escape_markdown(context.user_data['write_person_name'])}*:\n\n{message}",
        parse_mode="Markdown",
        reply_markup=keyboard,
    )
    return WRITE_CONFIRM

async def write_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    if query.data == "write_edit":
        await query.edit_message_text(
            f"✏️ Okay, send your updated message for "
            f"*{_escape_markdown(context.user_data['write_person_name'])}*:",
            parse_mode="Markdown",
        )
        return WRITE_TYPE_MESSAGE

    db.upsert_wish(
        wisher_id          = context.user_data["write_my_id"],
        birthday_person_id = context.user_data["write_person_id"],
        target_month       = context.user_data["write_target_month"],
        message            = context.user_data["write_message"],
    )
    await query.edit_message_text(
        f"🎉 Your wish for *{_escape_markdown(context.user_data['write_person_name'])}* "
        f"has been saved! They'll love it. 💌",
        parse_mode="Markdown",
    )
    context.user_data.clear()
    return ConversationHandler.END


# -------------------- /COLLATE FLOW --------------------

@admin_only
async def collate_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    month_num = (date.today().month % 12) + 1
    target    = next_month_str()
    babies    = db.get_birthdays_in_month(month_num)   # active users only

    if not babies:
        await update.message.reply_text(f"No birthdays found for next month ({target}).")
        return ConversationHandler.END

    context.user_data["collate_target_month"] = target
    await update.message.reply_text(
        "📋 *Collate Wishes*\n\nSelect a birthday person to generate their card:",
        parse_mode="Markdown",
        reply_markup=_bday_baby_keyboard(babies, "collate_person"),
    )
    return COLLATE_SELECT_PERSON[0]

async def collate_person_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    person_id = int(query.data.split(":", 1)[1])

    person = db.get_user_by_id(person_id)
    if not person:
        await query.edit_message_text("User not found.")
        return ConversationHandler.END

    target = context.user_data.get("collate_target_month", next_month_str())
    wishes = db.get_wishes_for_person(person_id, target)

    await query.edit_message_text(
        f"⏳ Generating card for *{_escape_markdown(person['name'])}*…", parse_mode="Markdown"
    )

    html_path = generate_card(person, wishes, target)
    with open(html_path, "rb") as f:
        await context.bot.send_document(
            chat_id  = update.effective_user.id,
            document = f,
            filename = f"birthday_card_{person['name'].replace(' ', '_')}_{target}.html",
            caption  = (
                f"🎂 Birthday card for *{_escape_markdown(person['name'])}* ({target})\n"
                f"_{len(wishes)} wish(es) included._"
            ),
            parse_mode="Markdown",
        )

    context.user_data.clear()
    return ConversationHandler.END


# -------------------- /ADMIN FLOW --------------------

@admin_only
async def admin_role_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    tg_id  = update.effective_user.id
    me     = db.get_user_by_telegram_id(tg_id)
    # Show all active users except the admin running the command
    users  = [u for u in db.get_all_active_users() if u["id"] != me["id"]]

    if not users:
        await update.message.reply_text("No other active users in the database.")
        return ConversationHandler.END

    await update.message.reply_text(
        "👥 *Change User Role*\n\nSelect the user whose role you want to change:",
        parse_mode="Markdown",
        reply_markup=_user_keyboard(users, "admin_user"),
    )
    return ADMIN_SELECT_USER

async def admin_user_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    user_id = int(query.data.split(":", 1)[1])
    user    = db.get_user_by_id(user_id)

    context.user_data["admin_target_id"]   = user_id
    context.user_data["admin_target_name"] = user["name"]

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("👑 Admin", callback_data="admin_role:admin"),
         InlineKeyboardButton("👤 Normal", callback_data="admin_role:normal")],
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel")],
    ])
    await query.edit_message_text(
        f"Set role for *{_escape_markdown(user['name'])}* (currently: _{user['role']}_):",
        parse_mode="Markdown",
        reply_markup=keyboard,
    )
    return ADMIN_SELECT_ROLE

async def admin_role_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    _, role = query.data.split(":", 1)

    db.set_user_role(context.user_data["admin_target_id"], role)
    await query.edit_message_text(
        f"✅ *{_escape_markdown(context.user_data['admin_target_name'])}*'s role has been updated to *{role}*.",
        parse_mode="Markdown",
    )
    context.user_data.clear()
    return ConversationHandler.END


# -------------------- /ADDUSER FLOW --------------------

@admin_only
async def adduser_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "➕ *Add New User*\n\n"
        "Step 1/4 — Enter their *Telegram handle* (e.g. `randomuser123`, without @):",
        parse_mode="Markdown",
    )
    return ADD_HANDLE

async def adduser_handle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    handle = update.message.text.strip().lstrip("@").lower()

    # Check both active and pending users — get_user_by_telehandle queries all rows
    if db.get_user_by_telehandle(handle):
        await update.message.reply_text(
            f"⚠️ `@{handle}` is already registered or pending activation. "
            "Enter a different handle:",
            parse_mode="Markdown",
        )
        return ADD_HANDLE

    context.user_data["add_handle"] = handle
    await update.message.reply_text(
        "Step 2/4 — Enter their *full name*:",
        parse_mode="Markdown",
    )
    return ADD_NAME

async def adduser_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["add_name"] = update.message.text.strip()
    await update.message.reply_text(
        "Step 3/4 — Enter their *birthday* in `DD/MM/YYYY` format (e.g. `25/12/1995`):",
        parse_mode="Markdown",
    )
    return ADD_BIRTHDAY

async def adduser_birthday(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    raw = update.message.text.strip()
    try:
        parts = raw.split("/")
        bday  = date(int(parts[2]), int(parts[1]), int(parts[0]))
        context.user_data["add_birthday"] = bday.strftime("%Y-%m-%d")
    except (ValueError, IndexError):
        await update.message.reply_text(
            "⚠️ Invalid date. Please use `DD/MM/YYYY` format:",
            parse_mode="Markdown",
        )
        return ADD_BIRTHDAY

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("👑 Admin",  callback_data="add_role:admin"),
         InlineKeyboardButton("👤 Normal", callback_data="add_role:normal")],
    ])
    await update.message.reply_text(
        "Step 4/4 — Select their *role*:",
        parse_mode="Markdown",
        reply_markup=keyboard,
    )
    return ADD_ROLE

async def adduser_role(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    _, role = query.data.split(":", 1)
    context.user_data["add_role"] = role

    d = context.user_data
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Confirm", callback_data="add_confirm"),
         InlineKeyboardButton("❌ Cancel",  callback_data="cancel")],
    ])
    await query.edit_message_text(
        f"📋 *Confirm new user:*\n\n"
        f"Handle: @{_escape_markdown(d['add_handle'])}\n"
        f"Name: *{_escape_markdown(d['add_name'])}*\n"
        f"Birthday: {_escape_markdown(d['add_birthday'])}\n"
        f"Role: {_escape_markdown(d['add_role'])}",
        parse_mode="Markdown",
        reply_markup=keyboard,
    )
    return ADD_CONFIRM

async def adduser_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    d = context.user_data
    # Insert into DB immediately as a pending user (telegram_id=NULL, pending=1).
    # Survives bot restarts — no bot_data involved.
    # activate_user() in auth.py fills in telegram_id when they send /start.
    db.add_pending_user(
        telehandle = d["add_handle"],
        name       = d["add_name"],
        birthday   = d["add_birthday"],
        role       = d["add_role"],
    )

    await query.edit_message_text(
        f"✅ *{_escape_markdown(d['add_name'])}* (@{_escape_markdown(d['add_handle'])}) has been added!\n\n"
        f"Ask them to open this bot and send /start to activate their account. 🔗",
        parse_mode="Markdown",
    )
    context.user_data.clear()
    return ConversationHandler.END


# -------------------- /REMOVEUSER FLOW --------------------

@admin_only
async def removeuser_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    tg_id = update.effective_user.id
    me    = db.get_user_by_telegram_id(tg_id)
    # Show ALL users (including pending) except the admin themselves,
    # so admins can remove mistaken pending entries too.
    users = [u for u in db.get_all_users() if u["id"] != me["id"]]

    if not users:
        await update.message.reply_text("No other users to remove.")
        return ConversationHandler.END

    await update.message.reply_text(
        "🗑️ *Remove User*\n\nSelect the user to remove:\n"
        "_⏳ = pending activation_",
        parse_mode="Markdown",
        reply_markup=_user_keyboard(users, "remove_user"),
    )
    return REMOVE_SELECT_USER

async def removeuser_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    user_id = int(query.data.split(":", 1)[1])
    user    = db.get_user_by_id(user_id)

    context.user_data["remove_id"]   = user_id
    context.user_data["remove_name"] = user["name"]

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🗑️ Yes, remove", callback_data="remove_confirm"),
         InlineKeyboardButton("❌ Cancel",       callback_data="cancel")],
    ])
    await query.edit_message_text(
        f"⚠️ Are you sure you want to remove *{_escape_markdown(user['name'])}*?\n"
        "_This will also delete all their wishes._",
        parse_mode="Markdown",
        reply_markup=keyboard,
    )
    return REMOVE_CONFIRM

async def removeuser_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    db.remove_user(context.user_data["remove_id"])
    await query.edit_message_text(
        f"✅ *{_escape_markdown(context.user_data['remove_name'])}* has been removed from the database.",
        parse_mode="Markdown",
    )
    context.user_data.clear()
    return ConversationHandler.END


# -------------------- WIRE UP STATE MAPS --------------------

from telegram.ext import MessageHandler, CallbackQueryHandler, filters

WRITE_STATES[WRITE_SELECT_PERSON] = [
    CallbackQueryHandler(write_person_selected, pattern=r"^write_person:"),
    CallbackQueryHandler(cancel,                pattern=r"^cancel$"),
]
WRITE_STATES[WRITE_TYPE_MESSAGE] = [
    MessageHandler(filters.TEXT & ~filters.COMMAND, write_message_received),
]
WRITE_STATES[WRITE_CONFIRM] = [
    CallbackQueryHandler(write_confirm, pattern=r"^write_(confirm|edit)$"),
    CallbackQueryHandler(cancel,        pattern=r"^cancel$"),
]

COLLATE_STATES[COLLATE_SELECT_PERSON[0]] = [
    CallbackQueryHandler(collate_person_selected, pattern=r"^collate_person:"),
    CallbackQueryHandler(cancel,                  pattern=r"^cancel$"),
]

ADMIN_STATES[ADMIN_SELECT_USER] = [
    CallbackQueryHandler(admin_user_selected, pattern=r"^admin_user:"),
    CallbackQueryHandler(cancel,              pattern=r"^cancel$"),
]
ADMIN_STATES[ADMIN_SELECT_ROLE] = [
    CallbackQueryHandler(admin_role_selected, pattern=r"^admin_role:"),
    CallbackQueryHandler(cancel,              pattern=r"^cancel$"),
]

ADDUSER_STATES[ADD_HANDLE] = [
    MessageHandler(filters.TEXT & ~filters.COMMAND, adduser_handle),
]
ADDUSER_STATES[ADD_NAME] = [
    MessageHandler(filters.TEXT & ~filters.COMMAND, adduser_name),
]
ADDUSER_STATES[ADD_BIRTHDAY] = [
    MessageHandler(filters.TEXT & ~filters.COMMAND, adduser_birthday),
]
ADDUSER_STATES[ADD_ROLE] = [
    CallbackQueryHandler(adduser_role, pattern=r"^add_role:"),
]
ADDUSER_STATES[ADD_CONFIRM] = [
    CallbackQueryHandler(adduser_confirm, pattern=r"^add_confirm$"),
    CallbackQueryHandler(cancel,          pattern=r"^cancel$"),
]

REMOVEUSER_STATES[REMOVE_SELECT_USER] = [
    CallbackQueryHandler(removeuser_selected, pattern=r"^remove_user:"),
    CallbackQueryHandler(cancel,              pattern=r"^cancel$"),
]
REMOVEUSER_STATES[REMOVE_CONFIRM] = [
    CallbackQueryHandler(removeuser_confirm, pattern=r"^remove_confirm$"),
    CallbackQueryHandler(cancel,             pattern=r"^cancel$"),
]
