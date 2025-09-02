import os
import re
import subprocess
import sys
import traceback
from inspect import signature
from io import StringIO
from time import time
from pyrogram import filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from DURGESH import app
from config import ADMINS

# --- Helpers ---

async def aexec(code: str, client, message: Message):
    # Build an async function __aexec(client, message) containing the provided code
    func_name = "__aexec"
    func_src = "async def {name}(client, message):\n".format(name=func_name) + "".join(
        f"\n {line}" for line in code.split("\n")
    )
    # Execute into controlled namespaces and retrieve the created function reliably
    locs = {}
    globs = globals()
    exec(func_src, globs, locs)
    return await locs[func_name](client, message)

async def edit_or_reply(msg: Message, **kwargs):
    func = msg.edit_text if getattr(msg.from_user, "is_self", False) else msg.reply
    sig = signature(func)
    spec = [p.name for p in sig.parameters.values() if p.name not in ("self", "cls")]
    await func(**{k: v for k, v in kwargs.items() if k in spec})

# --- /eval ---

@app.on_edited_message(
    filters.command("eval")
    & filters.user(ADMINS)
    & ~filters.forwarded
    & ~filters.via_bot
)
@app.on_message(
    filters.command(["eval", "ev"], prefixes=["/", "!", ".", ""])
    & filters.user(ADMINS)
    & ~filters.forwarded
    & ~filters.via_bot
)
async def executor(client: app, message: Message):
    if len(message.command) < 2:
        return await edit_or_reply(message, text="<b>ᴡʜᴀᴛ ʏᴏᴜ ᴡᴀɴɴᴀ ᴇxᴇᴄᴜᴛᴇ ʙᴀʙʏ ?</b>")

    try:
        cmd = message.text.split(" ", maxsplit=1)[15]
    except IndexError:
        return await message.delete()

    t1 = time()
    old_stderr, old_stdout = sys.stderr, sys.stdout
    redirected_output = sys.stdout = StringIO()
    redirected_error = sys.stderr = StringIO()

    exc_text = None
    try:
        await aexec(cmd, client, message)
    except Exception:
        exc_text = traceback.format_exc()
    finally:
        stdout = redirected_output.getvalue()
        stderr = redirected_error.getvalue()
        sys.stdout = old_stdout
        sys.stderr = old_stderr

    evaluation = "\n"
    if exc_text:
        evaluation += exc_text
    elif stderr:
        evaluation += stderr
    elif stdout:
        evaluation += stdout
    else:
        evaluation += "Success"

    final_output = f"<b>⥤ ʀᴇsᴜʟᴛ :</b>\n<pre language='python'>{evaluation}</pre>"

    t2 = time()
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    text="⏳", callback_data=f"runtime {round(t2 - t1, 3)} Seconds"
                ),
                InlineKeyboardButton(
                    text="🗑", callback_data=f"forceclose abc|{message.from_user.id}"
                ),
            ]
        ]
    )

    if len(final_output) > 4096:
        filename = "output.txt"
        with open(filename, "w+", encoding="utf8") as out_file:
            out_file.write(str(evaluation))

        await message.reply_document(
            document=filename,
            caption=f"<b>⥤ ᴇᴠᴀʟ :</b>\n<code>{cmd[0:980]}</code>\n\n<b>⥤ ʀᴇsᴜʟᴛ :</b>\nAttached Document",
            quote=False,
            reply_markup=keyboard,
        )
        await message.delete()
        os.remove(filename)
    else:
        await edit_or_reply(message, text=final_output, reply_markup=keyboard)

# --- callbacks ---

@app.on_callback_query(filters.regex(r"runtime"))
async def runtime_func_cq(_, cq):
    runtime = cq.data.split(None, 1)[15]
    await cq.answer(runtime, show_alert=True)

@app.on_callback_query(filters.regex("forceclose"))
async def forceclose_command(_, CallbackQuery):
    callback_data = CallbackQuery.data.strip()
    callback_request = callback_data.split(None, 1)[15]
    query, user_id = callback_request.split("|")
    if CallbackQuery.from_user.id != int(user_id):
        try:
            return await CallbackQuery.answer(
                "» ɪᴛ'ʟʟ ʙᴇ ʙᴇᴛᴛᴇʀ ɪғ ʏᴏᴜ sᴛᴀʏ ɪɴ ʏᴏᴜʀ ʟɪᴍɪᴛs ʙᴀʙʏ.", show_alert=True
            )
        except:
            return
    await CallbackQuery.message.delete()
    try:
        await CallbackQuery.answer()
    except:
        return

# --- /sh ---

@app.on_edited_message(
    filters.command("sh")
    & filters.user(ADMINS)
    & ~filters.forwarded
    & ~filters.via_bot
)
@app.on_message(
    filters.command(["sh"], prefixes=["/", "!", ".", ""])
    & filters.user(ADMINS)
    & ~filters.forwarded
    & ~filters.via_bot
)
async def shellrunner(_, message: Message):
    if len(message.command) < 2:
        return await edit_or_reply(message, text="<b>ᴇxᴀᴍᴩʟᴇ :</b>\n/sh git pull")

    text = message.text.split(None, 1)[15]

    def run_once(cmd_parts):
        try:
            proc = subprocess.Popen(
                cmd_parts, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            out_b, err_b = proc.communicate()
            out = out_b.decode("utf-8", errors="ignore")
            err = err_b.decode("utf-8", errors="ignore")
            return out if out.strip() else err if err.strip() else ""
        except Exception:
            return traceback.format_exc()

    if "\n" in text:
        lines = [ln for ln in text.split("\n") if ln.strip()]
        outputs = []
        for x in lines:
            parts = re.split(r""" (?=(?:[^'"]|'[^']*'|"[^"]*")*$)""", x)
            parts = [p.replace('"', "") for p in parts]
            outputs.append(f"$ {x}\n{run_once(parts)}")
        output = "\n".join(outputs)
    else:
        parts = re.split(r""" (?=(?:[^'"]|'[^']*'|"[^"]*")*$)""", text)
        parts = [p.replace('"', "") for p in parts]
        output = run_once(parts)

    if not output or output == "\n":
        output = "None"

    if len(output) > 4096:
        with open("output.txt", "w+", encoding="utf-8") as file:
            file.write(output)
        await app.send_document(
            message.chat.id,
            "output.txt",
            reply_to_message_id=message.id,
            caption="<code>Output</code>",
        )
        os.remove("output.txt")
    else:
        await edit_or_reply(message, text=f"<b>OUTPUT :</b>\n<pre>{output}</pre>")

    await message.stop_propagation()
