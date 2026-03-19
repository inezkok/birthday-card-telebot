import os
import tempfile
from pathlib import Path

from utils.date_utils import month_label

# -------------------- CONFETTI PALETTE --------------------
# These colours are injected into the JS in templates/card.html.
CONFETTI_COLOURS = ["#FFD700", "#FF6B9D", "#C77DFF", "#06D6A0", "#FFB347", "#74C0FC"]

# -------------------- TEMPLATE PATH --------------------
_TEMPLATE_PATH = Path(__file__).parent.parent / "templates" / "card.html"


# -------------------- PUBLIC ENTRY POINT --------------------

def generate_card(person, wishes, target_month: str) -> str:
    """
    Build the birthday card HTML file.

    Parameters
    ----------
    person       : sqlite3.Row with at least 'name' and 'birthday' fields
    wishes       : list of sqlite3.Row, each with 'wisher_name' and 'message'
    target_month : 'YYYY-MM' string (e.g. '2025-04')

    Returns
    -------
    Absolute path to the written temp file.
    """
    name         = person["name"]
    bday_display = _format_birthday(person["birthday"])  # e.g. "13 Apr"
    month_str    = month_label(target_month)              # e.g. "April 2025"
    wish_count   = len(wishes)
    wish_word    = "wish" if wish_count == 1 else "wishes"

    template = _TEMPLATE_PATH.read_text(encoding="utf-8")

    html = template.format(
        name         = name,
        bday_display = bday_display,
        month_str    = month_str,
        wish_count   = wish_count,
        wish_word    = wish_word,
        wish_cards   = _wish_cards_html(wishes),
        confetti_js  = _confetti_js(),
    )

    tmp = tempfile.NamedTemporaryFile(
        mode     = "w",
        suffix   = ".html",
        prefix   = f"bday_card_{name.replace(' ', '_')}_",
        delete   = False,
        encoding = "utf-8",
    )
    tmp.write(html)
    tmp.close()
    return tmp.name

# -------------------- PRIVATE HELPERS --------------------

def _format_birthday(birthday_iso: str) -> str:
    """Convert 'YYYY-MM-DD' to a short display string like '13 Apr'."""
    _month_abbr = ["Jan","Feb","Mar","Apr","May","Jun",
                   "Jul","Aug","Sep","Oct","Nov","Dec"]
    parts = birthday_iso.split("-")
    return f"{int(parts[2])} {_month_abbr[int(parts[1]) - 1]}"

def _wish_cards_html(wishes) -> str:
    """Render one <div class='wish-card'> block per wish."""
    if not wishes:
        return (
            '<div class="no-wishes">'
            '<p>No wishes yet — but the best ones are yet to come! 🌟</p>'
            '</div>'
        )

    blocks = []
    for w in wishes:
        name    = w["wisher_name"]
        handle = w["telehandle"]
        message = w["message"].replace("\n", "<br>")
        blocks.append(f"""
        <div class="wish-card">
          <div class="wish-avatar">{name[0].upper()}</div>
          <div class="wish-body">
            <div class="wish-author">{name} <span class="wish-handle">@{handle}</span></div>
            <div class="wish-text">{message}</div>
          </div>
        </div>""")

    return "\n".join(blocks)

def _confetti_js() -> str:
    """Return the self-contained confetti animation as a JS string."""
    colours = CONFETTI_COLOURS
    return f"""
        const COLOURS = {colours};

        function launchConfetti() {{
        const canvas = document.getElementById('confetti-canvas');
        const ctx    = canvas.getContext('2d');
        canvas.width  = window.innerWidth;
        canvas.height = window.innerHeight;

        const pieces = Array.from({{ length: 120 }}, () => ({{
            x:            Math.random() * canvas.width,
            y:            Math.random() * -canvas.height,
            r:            Math.random() * 8 + 4,
            colour:       COLOURS[Math.floor(Math.random() * COLOURS.length)],
            tilt:         Math.random() * 10 - 5,
            tiltAngleInc: Math.random() * 0.07 + 0.05,
            tiltAngle:    0,
            speed:        Math.random() * 2 + 1,
        }}));

        let frame = 0;

        function draw() {{
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            pieces.forEach(p => {{
            ctx.beginPath();
            ctx.lineWidth   = p.r / 2;
            ctx.strokeStyle = p.colour;
            ctx.moveTo(p.x + p.tilt + p.r / 4, p.y);
            ctx.lineTo(p.x + p.tilt,            p.y + p.tilt + p.r / 4);
            ctx.stroke();

            p.tiltAngle += p.tiltAngleInc;
            p.y    += Math.cos(frame / 15) + p.speed;
            p.x    += Math.sin(frame / 100) * 1.2;
            p.tilt  = Math.sin(p.tiltAngle) * 12;

            if (p.y > canvas.height) {{
                p.y = -10;
                p.x = Math.random() * canvas.width;
            }}
            }});
            frame++;
            if (frame < 400) requestAnimationFrame(draw);
            else ctx.clearRect(0, 0, canvas.width, canvas.height);
        }}

        draw();
        }}
    """
