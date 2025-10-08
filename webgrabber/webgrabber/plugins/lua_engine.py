# webgrabber/webgrabber/plugins/lua_runner.py

import asyncio
import lupa


async def run_lua_plugin(page, script_path):
    with open(script_path, 'r') as f:
        script = f.read()
    lua = lupa.LuaRuntime()
    func = lua.eval(script)
    context = {
        'click': lambda sel: asyncio.create_task(page.click(sel)),
        'press': lambda key: asyncio.create_task(page.keyboard.press(key))
    }
    await func(context)