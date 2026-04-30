"""
utils/card_generator.py – Generates a birthday card HTML file
==============================================================
The HTML structure, CSS, and layout all live in templates/card.html.
This file only handles:
  - building the wish card HTML blocks
  - filling the template placeholders
  - writing the result to a temp file
  - the confetti JS (kept here since it depends on CONFETTI_COLOURS)

To customise the card's look, edit templates/card.html.
To change confetti colours, edit CONFETTI_COLOURS below.

Error Handling
--------------
generate_card() may raise exceptions if:
  - Template file is missing or unreadable
  - File system errors occur when writing temp file
  - Data validation fails

Handlers should catch these and provide user feedback via send_error_message().
"""

import logging
import os
import tempfile
from pathlib import Path

from utils.date_utils import month_label

logger = logging.getLogger(__name__)

# ── Confetti palette ──────────────────────────────────────────────────────────
# These colours are injected into the JS in templates/card.html.
CONFETTI_COLOURS = ["#FFD700", "#FF6B9D", "#C77DFF", "#06D6A0", "#FFB347", "#74C0FC"]

# ── Template path ─────────────────────────────────────────────────────────────
_TEMPLATE_PATH = Path(__file__).parent.parent / "templates" / "card.html"


# ── Public entry point ────────────────────────────────────────────────────────

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
    
    Raises
    ------
    FileNotFoundError : if template file cannot be read
    IOError : if temp file cannot be written
    ValueError : if data is invalid
    """
    try:
        name = person.get("name", "Birthday Person")
        if not name:
            raise ValueError("Person name is required")
            
        bday_display = _format_birthday(person.get("birthday", "1900-01-01"))
        month_str = month_label(target_month)
        wish_count = len(wishes) if wishes else 0
        wish_word = "wish" if wish_count == 1 else "wishes"

        try:
            template = _TEMPLATE_PATH.read_text(encoding="utf-8")
        except FileNotFoundError as e:
            logger.error(f"Template file not found: {_TEMPLATE_PATH}")
            raise
        except IOError as e:
            logger.error(f"Failed to read template file: {e}")
            raise

        try:
            html = template.format(
                name=name,
                bday_display=bday_display,
                month_str=month_str,
                wish_count=wish_count,
                wish_word=wish_word,
                wish_cards=_wish_cards_html(wishes),
                confetti_js=_confetti_js(),
            )
        except KeyError as e:
            logger.error(f"Template formatting error - missing key: {e}")
            raise ValueError(f"Invalid template structure: {e}")
        except Exception as e:
            logger.error(f"Error formatting template: {e}")
            raise

        try:
            tmp = tempfile.NamedTemporaryFile(
                mode="w",
                suffix=".html",
                prefix=f"bday_card_{name.replace(' ', '_')}_",
                delete=False,
                encoding="utf-8",
            )
            tmp.write(html)
            tmp.close()
            logger.info(f"Generated birthday card: {tmp.name}")
            return tmp.name
        except IOError as e:
            logger.error(f"Failed to write temporary card file: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error while creating card file: {e}")
            raise
    except Exception as e:
        logger.exception("Error in generate_card")
        raise


# ── Private helpers ───────────────────────────────────────────────────────────

def _format_birthday(birthday_iso: str) -> str:
    """Convert 'YYYY-MM-DD' to a short display string like '13 Apr'."""
    try:
        _month_abbr = ["Jan","Feb","Mar","Apr","May","Jun",
                       "Jul","Aug","Sep","Oct","Nov","Dec"]
        parts = birthday_iso.split("-")
        if len(parts) != 3:
            raise ValueError(f"Invalid birthday format: {birthday_iso}")
        month_idx = int(parts[1]) - 1
        if month_idx < 0 or month_idx >= 12:
            raise ValueError(f"Invalid month: {parts[1]}")
        return f"{int(parts[2])} {_month_abbr[month_idx]}"
    except Exception as e:
        logger.warning(f"Error formatting birthday {birthday_iso}: {e}")
        return "Date TBD"


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
        try:
            name = w.get("wisher_name", "Anonymous")
            message = w.get("message", "")
            if not message:
                continue
            message = message.replace("\n", "<br>")
            blocks.append(f"""
        <div class="wish-card">
          <div class="wish-avatar">{name[0].upper()}</div>
          <div class="wish-body">
            <div class="wish-author">{name}</div>
            <div class="wish-text">{message}</div>
          </div>
        </div>""")
        except Exception as e:
            logger.warning(f"Error processing wish card: {e}")
            continue

    return "\n".join(blocks) if blocks else (
        '<div class="no-wishes">'
        '<p>No wishes could be rendered.</p>'
        '</div>'
    )


def _confetti_js() -> str:
    """Return the self-contained confetti animation as a JS string."""
    try:
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
    except Exception as e:
        logger.error(f"Error generating confetti JS: {e}")
        return ""
