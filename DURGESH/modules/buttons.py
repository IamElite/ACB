# ... existing code ...
def extract_chat_and_msg_id(link: str) -> Tuple[Optional[int], Optional[int]]:
    if priv := re.match(r"https?://t\.me/c/(-?\d+)/(\d+)", link.strip()):
        raw = priv.group(1).lstrip("-")
        return (int(f"-{raw}") if raw.startswith("100") else int(f"-100{raw}")), int(priv.group(2))
    return None, None

def get_forward_chat(msg: Optional[Message]):
    """Safely extracts forward chat avoiding deprecation warnings on forward_from_chat."""
    if not msg:
        return None
    origin = getattr(msg, "forward_origin", None)
    if origin:
        chat = getattr(origin, "chat", None)
        if chat:
            return getattr(chat, "sender_chat", chat)
        sender = getattr(origin, "sender_chat", None)
        if sender:
            return sender
    if not hasattr(msg, "forward_origin"):
        try:
            return getattr(msg, "forward_from_chat", None)
        except Exception:
            return None
    return None

def is_forwarded_post(msg: Message) -> bool:
    """Checks if a message is forwarded without triggering warnings."""
    if getattr(msg, "forward_origin", None) is not None:
        return True
    return bool(getattr(msg, "forward_date", None))

async def safe_copy_and_delete(msg: Message, chat_id: int, caption: Optional[str] = None, reply_markup: Optional[InlineKeyboardMarkup] = None) -> Optional[Message]:
# ... existing code ...
def parse_buttons(text: str, font_style: str = "sim", default_color=RED_STYLE) -> Optional[InlineKeyboardMarkup]:
    """Parses button templates, preserving titles containing '+' and applying default red styling."""
    if not text:
        return None
    lines = re.sub(r'\]\[', ']\n[', text.strip()).splitlines()
    keyboard = []

    # Exactly 2 capturing groups: (1) button content, (2) trailing color code
    BUTTON_REGEX = re.compile(r'\[([^\]]+)\](?:\s*[:\-–—|]?\s*\[?\(?([a-zA-Z]+)\)?\]?)?')

    for line in lines:
        if not line.strip():
            continue
        row = []
        for content, out_color in BUTTON_REGEX.findall(line):
            color_suffix = (out_color or "").strip().lower()
            match = URL_REGEX.search(content)
            if match:
                label = re.sub(r'[\s+|:–—\->]+$', '', content[:match.start()]).strip()
                raw_url = match.group(1).strip()
                in_color = re.sub(r'^[\s+|:–—\->]+', '', content[match.end():]).strip().lower()
            else:
                parts = re.split(r'\s+(?:\+|\->|\|)\s+', content)
                if len(parts) < 2:
                    continue
                label, raw_url = parts[0].strip(), parts[1].strip()
                in_color = parts[2].strip().lower() if len(parts) > 2 else ""

            if not label or not (clean_url := sanitize_button_url(raw_url)):
                continue

            btn_color = COLOR_MAP.get(in_color or color_suffix, default_color)
            styled_text = apply_font(label, font_style) if font_style != "normal" else label
            row.append(create_button(styled_text, clean_url, style=btn_color))

        if row:
            keyboard.append(row)
    return InlineKeyboardMarkup(keyboard) if keyboard else None

ENTITY_TAGS = {
# ... existing code ...
    needs_link = bool(re.search(r"\{\s*(?:link|url|target)\s*\}", tmpl_data.get("template", ""), re.IGNORECASE))

    if needs_link and not extracted_url:
        if settings.get("forward_tag_removal") and is_forwarded_post(message):
            await safe_copy_and_delete(message, chat_id)
        return

    font_style = tmpl_data.get("font_style", "sim")
    btn_text = tmpl_data.get("template", "")
    if extracted_url:
        btn_text = re.sub(r"\{\s*(?:link|url|target)\s*\}", extracted_url, btn_text, flags=re.IGNORECASE)

    keyboard = parse_buttons(btn_text, font_style=font_style, default_color=RED_STYLE)
    if not keyboard:
        return

    final_caption = apply_font_to_caption(cl_html, font_style) if font_style != "normal" else cl_html

    # If forwarded post tag removal is enabled
    if settings.get("forward_tag_removal") and is_forwarded_post(message):
        await safe_copy_and_delete(message, chat_id, caption=final_caption, reply_markup=keyboard)
        return

    # Attempt in-place editing; fallback to clone-and-replace if bot lacks editing rights of another admin
# ... existing code ...
