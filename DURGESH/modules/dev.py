import os
import re
import subprocess
import sys
import time
import traceback
from inspect import getfullargspec
from io import StringIO
from time import time

from pyrogram import filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from config import OWNER_ID
from DURGESH import app
from DURGESH.database.extra import protect_message


async def aexec(code, client, message):
    # Prepare the code with correct indentation inside an async function
    indented_code = "\n    ".join(code.split("\n"))
    exec_code = f"async def __aexec(client, message):\n    {indented_code}"
    
    # Dictionary to capture local variables from exec()
    exec_locals = {}
    
    try:
        exec(exec_code, globals(), exec_locals)
    except:
        raise  # Propagate the exception
    
    # Check if __aexec was defined
    if "__aexec" not in exec_locals:
        raise KeyError("The '__aexec' function was not defined in the dynamic code.")
    
    # Execute the dynamic function and return its result
    func = exec_locals["__aexec"]
    return await func(client, message)  # Return the function's return value


async def edit_or_reply(msg: Message, **kwargs):
    func = msg.edit_text if msg.from_user.is_self else msg.reply
    spec = getfullargspec(func.__wrapped__).args
    await func(**{k: v for k, v in kwargs.items() if k in spec})
    await protect_message(msg.chat.id, msg.id)


@app.on_edited_message(
    filters.command(["ev", "eval"])
    & filters.user(OWNER_ID)
    & ~filters.forwarded
    & ~filters.via_bot
)
@app.on_message(
    filters.command(["ev", "eval", "dev"], prefixes=["/", "!", "", "."]) & filters.user(OWNER_ID) & ~filters.forwarded & ~filters.via_bot
)
async def executor(client: app, message: Message):
    if len(message.command) < 2:
        return await edit_or_reply(message, text="<b>ᴡʜᴀᴛ ʏᴏᴜ ᴡᴀɴɴᴀ ᴇxᴇᴄᴜᴛᴇ ʙᴀʙʏ ?</b>")
    try:
        cmd = message.text.split(" ", maxsplit=1)[1]
    except IndexError:
        return await message.delete()
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
    except Exception:
        exc = traceback.format_exc()
    finally:
        sys.stdout, sys.stderr = old_stdout, old_stderr
    
    stdout = redirected_output.getvalue().strip()
    stderr = redirected_error.getvalue().strip()
    
    evaluation = ""
    if exc:
        evaluation = exc.strip()
    else:
        parts = []
        if stderr.strip():
            parts.append(stderr.strip())
        if stdout.strip():
            parts.append(stdout.strip())
        if result is not None:
            parts.append(f"Return Value: {result!r}")
        evaluation = "\n\n".join(parts) if parts else "Success"
    
    final_output = f"<b>⥤ ʀᴇsᴜʟᴛ :</b>\n<pre language='python'>{evaluation}</pre>"
    
    if len(final_output) > 4096:
        filename = "output.txt"
        with open(filename, "w+", encoding="utf8") as out_file:
            out_file.write(str(evaluation))
        t2 = time()
        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        text="⏳",
                        callback_data=f"runtime {t2-t1:.3f} Seconds",
                    )
                ]
            ]
        )
        await message.reply_document(
            document=filename,
            caption=f"<b>⥤ ᴇᴠᴀʟ :</b>\n<code>{cmd[:980]}</code>\n\n<b>⥤ ʀᴇsᴜʟᴛ :</b>\nAttached Document",
            quote=False,
            reply_markup=keyboard,
        )
        await message.delete()
        os.remove(filename)
    else:
        t2 = time()
        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        text="⏳",
                        callback_data=f"runtime {t2-t1:.3f} Seconds",
                    ),
                    InlineKeyboardButton(
                        text="🗑",
                        callback_data=f"forceclose abc|{message.from_user.id}",
                    ),
                ]
            ]
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
                "» ɪᴛ'ʟʟ ʙᴇ ʙᴇᴛᴛᴇʀ ɪғ ʏᴏᴜ sᴛᴀʏ ɪɴ ʏᴏᴜʀ ʟɪᴍɪᴛs ʙᴀʙʏ.", show_alert=True
            )
        except:
            return
    await CallbackQuery.message.delete()
    try:
        await CallbackQuery.answer()
    except:
        return


@app.on_edited_message(
    filters.command("sh")
    & filters.user(OWNER_ID)
    & ~filters.forwarded
    & ~filters.via_bot
)
@app.on_message(filters.command(["sh", "de"], prefixes=["/", "!", "", "."]) & filters.user(OWNER_ID) & ~filters.forwarded & ~filters.via_bot)
async def shellrunner(_, message: Message):
    if len(message.command) < 2:
        return await edit_or_reply(message, text="<b>ᴇxᴀᴍᴩʟᴇ :</b>\n/sh git pull")
    text = message.text.split(None, 1)[1]
    if "\n" in text:
        code = text.split("\n")
        output = ""
        for x in code:
            shell = re.split(""" (?=(?:[^'"]|'[^']*'|"[^"]*")*$)""", x)
            try:
                process = subprocess.Popen(
                    shell,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
            except Exception as err:
                await edit_or_reply(message, text=f"<b>ᴇʀʀᴏʀ :</b>\n<pre>{err}</pre>")
                continue
            output += f"<b>{x}</b>\n"
            output += process.stdout.read().decode("utf-8").strip()
            output += "\n"
    else:
        shell = re.split(""" (?=(?:[^'"]|'[^']*'|"[^"]*")*$)""", text)
        for a in range(len(shell)):
            shell[a] = shell[a].replace('"', "")
        try:
            process = subprocess.Popen(
                shell,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except Exception as err:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            errors = traceback.format_exception(
                etype=exc_type,
                value=exc_obj,
                tb=exc_tb,
            )
            return await edit_or_reply(
                message, text=f"<b>ᴇʀʀᴏʀ :</b>\n<pre>{''.join(errors)}</pre>"
            )
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
                caption="<code>ᴏᴜᴛᴘᴜᴛ</code>",
            )
            return os.remove("output.txt")
        await edit_or_reply(message, text=f"<b>ᴏᴜᴛᴘᴜᴛ :</b>\n<pre>{output}</pre>")
    else:
        await edit_or_reply(message, text="<b>ᴏᴜᴛᴘᴜᴛ :</b>\n<code>ɴᴏᴛʜɪɴɢ ᴛᴏ sʜᴏᴡ</code>")
    await message.stop_propagation()
