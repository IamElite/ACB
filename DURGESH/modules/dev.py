import os
import re
import subprocess
import sys
import traceback
import importlib
from inspect import signature
from io import StringIO
from time import time
import types

from pyrogram import filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from DURGESH import app
from config import ADMINS


# Store execution contexts
eval_contexts = {}


async def aexec(code, client, message):
    # Create a unique module name for this execution
    module_name = f"eval_module_{message.id}_{int(time())}"
    
    # Create module namespace
    module_globals = {
        '__name__': module_name,
        '__builtins__': __builtins__,
        'client': client,
        'message': message,
        'app': app,
    }
    
    # Add commonly used modules
    import asyncio
    import aiohttp
    import json
    import requests
    module_globals.update({
        'asyncio': asyncio,
        'aiohttp': aiohttp,
        'json': json,
        'requests': requests,
    })
    
    # Create the async function code with proper indentation
    func_code = "async def __aexec(client, message):\n"
    for line in code.split('\n'):
        func_code += f"    {line}\n"
    
    # Execute in the module namespace
    exec(func_code, module_globals)
    
    # Get and call the function
    __aexec = module_globals['__aexec']
    return await __aexec(client, message)


def install_package(package_name):
    """Install a package using pip"""
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package_name])
        return True
    except subprocess.CalledProcessError:
        return False


async def edit_or_reply(msg: Message, **kwargs):
    func = msg.edit_text if msg.from_user.is_self else msg.reply
    sig = signature(func)
    spec = [param.name for param in sig.parameters.values() if param.name not in ('self', 'cls')]
    await func(**{k: v for k, v in kwargs.items() if k in spec})


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
async def executor(client, message: Message):
    if len(message.command) < 2:
        return await edit_or_reply(message, text="<b>ᴡʜᴀᴛ ʏᴏᴜ ᴡᴀɴɴᴀ ᴇxᴇᴄᴜᴛᴇ ʙᴀʙʏ ?</b>")
    try:
        cmd = message.text.split(" ", maxsplit=1)[1]
    except IndexError:
        return await message.delete()

    # Store the original code for this message
    eval_contexts[message.id] = {
        'code': cmd,
        'timestamp': time()
    }
    
    await execute_code(client, message, cmd)


@app.on_edited_message(
    filters.create(lambda _, __, msg: msg.id in eval_contexts)
    & filters.user(ADMINS)
    & ~filters.forwarded
    & ~filters.via_bot
)
async def edit_executor(client, message: Message):
    # Get the updated code from the edited message
    if message.text and len(message.text.split(" ", 1)) > 1:
        cmd = message.text.split(" ", maxsplit=1)[1]
        # Update the stored code
        eval_contexts[message.id] = {
            'code': cmd,
            'timestamp': time()
        }
        await execute_code(client, message, cmd)


async def execute_code(client, message: Message, cmd):
    t1 = time()
    old_stderr = sys.stderr
    old_stdout = sys.stdout
    redirected_output = sys.stdout = StringIO()
    redirected_error = sys.stderr = StringIO()
    stdout, stderr, exc = None, None, None

    max_attempts = 3  # Prevent infinite loops
    attempts = 0
    
    while attempts < max_attempts:
        try:
            await aexec(cmd, client, message)
            break  # Success, exit loop
        except ModuleNotFoundError as e:
            # Extract module name from error
            module_name = str(e).split("'")[1] if "'" in str(e) else str(e)
            
            # Try to install the missing module
            await edit_or_reply(message, text=f"<b>Installing missing module:</b> <code>{module_name}</code>")
            
            if install_package(module_name):
                # Try to import the module to make it available
                try:
                    importlib.import_module(module_name)
                except:
                    pass
                attempts += 1
                continue  # Retry execution
            else:
                exc = f"Failed to install module: {module_name}\n{str(e)}"
                break
        except Exception:
            exc = traceback.format_exc()
            break

    stdout = redirected_output.getvalue()
    stderr = redirected_error.getvalue()
    sys.stdout = old_stdout
    sys.stderr = old_stderr

    evaluation = "\n"
    if exc:
        evaluation += exc
    elif stderr:
        evaluation += stderr
    elif stdout:
        evaluation += stdout
    else:
        evaluation += "Success"

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
                        callback_data=f"runtime {round(t2-t1, 3)} Seconds",
                    )
                ]
            ]
        )
        await message.reply_document(
            document=filename,
            caption=f"<b>⥤ ᴇᴠᴀʟ :</b>\n<code>{cmd[:980]}</code>\n\n<b>⥤ ʀᴇsᴜʟᴛ :</b>\nAttached Document",
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
                        callback_data=f"runtime {round(t2-t1, 3)} Seconds",
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
    
    text = message.text.split(None, 1)[1]
    if "\n" in text:
        code = text.split("\n")
        output = ""
        for x in code:
            shell = re.split(r''' (?=(?:[^'"]|'[^']*'|"[^"]*")*$)''', x)
            try:
                process = subprocess.Popen(
                    shell,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
            except Exception as err:
                await edit_or_reply(message, text=f"<b>ERROR :</b>\n<pre>{err}</pre>")
                continue
            output += f"<b>{x}</b>\n"
            output += process.stdout.read()[:-1].decode("utf-8")
            output += "\n"
    else:
        shell = re.split(r''' (?=(?:[^'"]|'[^']*'|"[^"]*")*$)''', text)
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
                message, text=f"<b>ERROR :</b>\n<pre>{''.join(errors)}</pre>"
            )
        output = process.stdout.read()[:-1].decode("utf-8")

    if str(output).strip() == "":
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
        else:
            await edit_or_reply(message, text=f"<b>OUTPUT :</b>\n<pre>{output}</pre>")
    else:
        await edit_or_reply(message, text="<b>OUTPUT :</b>\n<code>None</code>")

    await message.stop_propagation()


# Cleanup old contexts periodically
async def cleanup_old_contexts():
    current_time = time()
    expired_keys = []
    for msg_id, context in eval_contexts.items():
        if current_time - context['timestamp'] > 3600:  # 1 hour old
            expired_keys.append(msg_id)
    
    for key in expired_keys:
        eval_contexts.pop(key, None)
