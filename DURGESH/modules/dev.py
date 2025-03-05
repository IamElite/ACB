import os
import re
import subprocess
import sys
import time
import traceback
from inspect import getfullargspec
from io import StringIO
from time import time

from pyrogram import Client, filters  # pyrofork drop‑in replacement ke liye "from pyrogram" use kar rahe hain
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from config import OWNER_ID
from DURGESH import app
from DURGESH.database.extra import protect_message

# Define PROTECTED_GLOBALS: Yeh list un sab globals ko rakhegi jo clear nahi karne hain.
PROTECTED_GLOBALS = {
    "__name__", "__file__", "__package__", "__doc__", "__loader__", "__spec__",
    "os", "re", "subprocess", "sys", "time", "traceback", "getfullargspec",
    "StringIO", "Client", "filters", "InlineKeyboardButton", "InlineKeyboardMarkup",
    "Message", "OWNER_ID", "app", "protect_message", "aexec", "edit_or_reply",
    "executor", "runtime_func_cq", "forceclose_command", "shellrunner",
    "eval_filter", "shell_filter", "clear_filter", "PROTECTED_GLOBALS"
}

async def aexec(code, client, message):
    # Code ko async function ke andar execute karne ke liye sahi indentation set karte hain
    indented_code = "\n ".join(code.split("\n"))
    exec_code = f"async def __aexec(client, message):\n {indented_code}"
    exec_locals = {}
    try:
        exec(exec_code, globals(), exec_locals)
    except Exception as e:
        raise Exception(f"Compilation Error: {e}")
    if "__aexec" not in exec_locals:
        raise KeyError("The '__aexec' function was not defined in the dynamic code.")
    func = exec_locals["__aexec"]
    return await func(client, message)

async def edit_or_reply(msg: Message, **kwargs):
    # Agar user ka message hai to edit karo, nahi to reply karo
    func = msg.edit_text if msg.from_user.is_self else msg.reply
    spec = getfullargspec(func.__wrapped__).args
    await func(**{k: v for k, v in kwargs.items() if k in spec})
    await protect_message(msg.chat.id, msg.id)

# Eval filter: command with prefixes (/ ! .) OR plain text starting with ev, eval, dev (case-insensitive)
eval_filter = (
    filters.command(["ev", "eval", "dev"], prefixes=["/", "!", "."]) |
    (filters.text & filters.regex(r"(?i)^(ev|eval|dev)(\s|$)"))
)

@app.on_edited_message(eval_filter & filters.user(OWNER_ID) & ~filters.forwarded & ~filters.via_bot)
@app.on_message(eval_filter & filters.user(OWNER_ID) & ~filters.forwarded & ~filters.via_bot)
async def executor(client: app, message: Message):
    if message.from_user.id != OWNER_ID:
        return
    cmd = ""
    if hasattr(message, "command") and message.command:
        if len(message.command) < 2:
            return await edit_or_reply(message, text="<b>What do you want to execute?</b>")
        try:
            cmd = message.text.split(" ", maxsplit=1)[1]
        except IndexError:
            return await message.delete()
    else:
        text = message.text.strip()
        parts = text.split(" ", maxsplit=1)
        if parts[0].lower() in ["ev", "eval", "dev"]:
            if len(parts) < 2:
                return await edit_or_reply(message, text="<b>What do you want to execute?</b>")
            cmd = parts[1]
        else:
            return

    t1 = time()
    old_stderr = sys.stderr
    old_stdout = sys.stdout
    redirected_output = StringIO()
    redirected_error = StringIO()
    result = None
    exc = None
    try:
        sys.stdout, sys.stderr = redirected_output, redirected_error
        result = await aexec(cmd, client, message)
    except Exception as e:
        # Simple error message without full traceback
        exc = f"Error: {str(e)}"
    finally:
        sys.stdout, sys.stderr = old_stdout, old_stderr
    stdout = redirected_output.getvalue().strip()
    stderr = redirected_error.getvalue().strip()
    evaluation = ""
    if exc:
        evaluation = exc
    else:
        parts = []
        if stderr:
            parts.append(stderr)
        if stdout:
            parts.append(stdout)
        if result is not None:
            parts.append(f"Return Value: {result!r}")
        evaluation = "\n\n".join(parts) if parts else "Success"
    final_output = f"<b>Result:</b>\n<pre language='python'>{evaluation}</pre>"
    if len(final_output) > 4096:
        filename = "output.txt"
        with open(filename, "w+", encoding="utf8") as out_file:
            out_file.write(evaluation)
        t2 = time()
        keyboard = InlineKeyboardMarkup(
            [[InlineKeyboardButton(text="⏳", callback_data=f"runtime {t2-t1:.3f} Seconds")]]
        )
        await message.reply_document(
            document=filename,
            caption=f"<b>Eval:</b>\n<code>{cmd[:980]}</code>\n\n<b>Result:</b>\nAttached Document",
            quote=False,
            reply_markup=keyboard,
        )
        await message.delete()
        os.remove(filename)
    else:
        t2 = time()
        keyboard = InlineKeyboardMarkup(
            [[
                InlineKeyboardButton(text="⏳", callback_data=f"runtime {t2-t1:.3f} Seconds"),
                InlineKeyboardButton(text="", callback_data=f"forceclose abc|{message.from_user.id}")
            ]]
        )
        await edit_or_reply(message, text=final_output, reply_markup=keyboard)

@app.on_callback_query(filters.regex(r"runtime"))
async def runtime_func_cq(_, cq):
    runtime = cq.data.split(None, 1)[1]
    await cq.answer(runtime, show_alert=True)

@app.on_callback_query(filters.regex("forceclose"))
async def forceclose_command(_, CallbackQuery):
    callback_data = CallbackQuery.data.strip()
    callback_request = callback_data.split(None, 1)[1]
    query, user_id = callback_request.split("|")
    if CallbackQuery.from_user.id != int(user_id):
        try:
            return await CallbackQuery.answer(
                "» It won't be better if you stay in your limits, baby.", show_alert=True
            )
        except:
            return
    await CallbackQuery.message.delete()
    try:
        await CallbackQuery.answer()
    except:
        return

# Shell filter: command with prefixes (/ ! .) OR plain text starting with sh or de (case-insensitive)
shell_filter = (
    filters.command(["sh", "de"], prefixes=["/", "!", "."]) |
    (filters.text & filters.regex(r"(?i)^(sh|de)(\s|$)"))
)

@app.on_edited_message(shell_filter & filters.user(OWNER_ID) & ~filters.forwarded & ~filters.via_bot)
@app.on_message(shell_filter & filters.user(OWNER_ID) & ~filters.forwarded & ~filters.via_bot)
async def shellrunner(_, message: Message):
    if message.from_user.id != OWNER_ID:
        return
    cmd = ""
    if hasattr(message, "command") and message.command:
        if len(message.command) < 2:
            return await edit_or_reply(message, text="<b>Example:</b>\n/sh git pull")
        try:
            cmd = message.text.split(" ", maxsplit=1)[1]
        except IndexError:
            return await message.delete()
    else:
        text = message.text.strip()
        parts = text.split(" ", maxsplit=1)
        if parts[0].lower() in ["sh", "de"]:
            if len(parts) < 2:
                return await edit_or_reply(message, text="<b>Example:</b>\n/sh git pull")
            cmd = parts[1]
        else:
            return

    if "\n" in cmd:
        code = cmd.split("\n")
        output = ""
        for x in code:
            shell_parts = re.split(r""" (?=(?:[^'"]|'[^']*'|"[^"]*")*$)""", x)
            try:
                process = subprocess.Popen(
                    shell_parts,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
            except Exception as err:
                await edit_or_reply(message, text=f"<b>Error:</b>\n<pre>{str(err)}</pre>")
                continue
            output += f"<b>{x}</b>\n"
            output += process.stdout.read().decode("utf-8").strip()
            output += "\n"
    else:
        shell_parts = re.split(r""" (?=(?:[^'"]|'[^']*'|"[^"]*")*$)""", cmd)
        for a in range(len(shell_parts)):
            shell_parts[a] = shell_parts[a].replace('"', "")
        try:
            process = subprocess.Popen(
                shell_parts,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except Exception as err:
            errors = f"Error: {str(err)}"
            return await edit_or_reply(message, text=f"<b>Error:</b>\n<pre>{errors}</pre>")
        output = process.stdout.read().decode("utf-8").strip()
        if not output:
            output = None

    if output:
        if len(output) > 4096:
            with open("output.txt", "w+") as file:
                file.write(output)
            await app.send_document(
                message.chat.id,
                "output.txt",
                reply_to_message_id=message.id,
                caption="<code>Output</code>",
            )
            os.remove("output.txt")
            return
        await edit_or_reply(message, text=f"<b>Output:</b>\n<pre>{output}</pre>")
    else:
        await edit_or_reply(message, text="<b>Output:</b>\n<code>Nothing to show</code>")
    await message.stop_propagation()

# Clear filter: command with prefixes (/ ! .) OR plain text starting with clear (case-insensitive)
clear_filter = (
    filters.command("clear", prefixes=["/", "!", "."]) |
    (filters.text & filters.regex(r"(?i)^clear(\s|$)"))
)

@app.on_edited_message(clear_filter & filters.user(OWNER_ID) & ~filters.forwarded & ~filters.via_bot)
@app.on_message(clear_filter & filters.user(OWNER_ID) & ~filters.forwarded & ~filters.via_bot)
async def clear_globals(_, message: Message):
    if message.from_user.id != OWNER_ID:
        return
    # Delete globals that are not in PROTECTED_GLOBALS and do not start with '__'
    keys_to_remove = [key for key in list(globals().keys()) if key not in PROTECTED_GLOBALS and not key.startswith("__")]
    for key in keys_to_remove:
        try:
            del globals()[key]
        except Exception:
            pass
    await edit_or_reply(message, text="<b>Cleared:</b> Dynamic changes removed. Global state reset.")
