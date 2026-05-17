file_path = 'kairos/api/routes/web.py'
with open(file_path, 'r') as f:
    lines = f.readlines()

# Remove lines 309 to 326 (indices 308 to 326) and replace with clean versions
# Lines are:
# 309:@router.put("/api/v1/journeys/{journey_id}")
# 310:
# 311:@router.delete("/api/v1/journeys/{journey_id}")
# 312:async def delete_journey_web(req: Request, journey_id: str):
# 313:    coach = await _get_coach(req)
# 314:    if not coach: return JSONResponse({"ok": False}, status_code=403)
# 315:    je = req.app.state.journey_engine
# 316:    ok = await je.delete_journey(journey_id)
# 317:    return {"ok": ok}
# 318:async def update_journey(req: Request, journey_id: str):
# 319:    coach = await _get_coach(req)
# 320:    if not coach: return JSONResponse({"ok": False}, status_code=403)
# 321:    body = await req.json()
# 322:    je = req.app.state.journey_engine
# 323:    j = await je.update_journey(journey_id, **body)
# 324:    return {"ok": True, "journey": j} if j else {"ok": False}

clean_block = [
    '@router.put("/api/v1/journeys/{journey_id}")\n',
    'async def update_journey(req: Request, journey_id: str):\n',
    '    coach = await _get_coach(req)\n',
    '    if not coach: return JSONResponse({"ok": False}, status_code=403)\n',
    '    body = await req.json()\n',
    '    je = req.app.state.journey_engine\n',
    '    j = await je.update_journey(journey_id, **body)\n',
    '    return {"ok": True, "journey": j} if j else {"ok": False}\n',
    '\n\n',
    '@router.delete("/api/v1/journeys/{journey_id}")\n',
    'async def delete_journey_web(req: Request, journey_id: str):\n',
    '    coach = await _get_coach(req)\n',
    '    if not coach: return JSONResponse({"ok": False}, status_code=403)\n',
    '    je = req.app.state.journey_engine\n',
    '    ok = await je.delete_journey(journey_id)\n',
    '    return {"ok": ok}\n'
]

# We want to replace from where @router.put was to where the old update_journey finished.
# Old update_journey finished at 324 in my previous grep.
new_lines = lines[:308] + clean_block + lines[324:]
with open(file_path, 'w') as f:
    f.writelines(new_lines)
