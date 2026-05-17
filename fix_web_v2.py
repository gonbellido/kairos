file_path = 'kairos/api/routes/web.py'
with open(file_path, 'r') as f:
    lines = f.readlines()

# It seems I did the same mistake again.
# Lines 339 to 355 need to be cleaned up.
# 339:@router.put("/api/v1/journeys/{phase_id}/phases")
# 340:
# 341:@router.put("/api/v1/journeys/phases/{phase_id}/reorder")
# 342:async def reorder_phase_web(req: Request, phase_id: str):
# 343:    coach = await _get_coach(req)
# 344:    if not coach: return JSONResponse({"ok": False}, status_code=403)
# 345:    body = await req.json()
# 346:    je = req.app.state.journey_engine
# 347:    ok = await je.reorder_phase(phase_id, direction=body.get("direction", "up"))
# 348:    return {"ok": ok}
# 349:async def update_phase(req: Request, phase_id: str):
# 350:    coach = await _get_coach(req)
# 351:    if not coach: return JSONResponse({"ok": False}, status_code=403)
# 352:    body = await req.json()
# 353:    je = req.app.state.journey_engine
# 354:    p = await je.update_phase(phase_id, **body)
# 355:    return {"ok": True, "phase": p} if p else {"ok": False}

clean_block = [
    '@router.put("/api/v1/journeys/{phase_id}/phases")\n',
    'async def update_phase(req: Request, phase_id: str):\n',
    '    coach = await _get_coach(req)\n',
    '    if not coach: return JSONResponse({"ok": False}, status_code=403)\n',
    '    body = await req.json()\n',
    '    je = req.app.state.journey_engine\n',
    '    p = await je.update_phase(phase_id, **body)\n',
    '    return {"ok": True, "phase": p} if p else {"ok": False}\n',
    '\n\n',
    '@router.put("/api/v1/journeys/phases/{phase_id}/reorder")\n',
    'async def reorder_phase_web(req: Request, phase_id: str):\n',
    '    coach = await _get_coach(req)\n',
    '    if not coach: return JSONResponse({"ok": False}, status_code=403)\n',
    '    body = await req.json()\n',
    '    je = req.app.state.journey_engine\n',
    '    ok = await je.reorder_phase(phase_id, direction=body.get("direction", "up"))\n',
    '    return {"ok": ok}\n'
]

new_lines = lines[:338] + clean_block + lines[355:]
with open(file_path, 'w') as f:
    f.writelines(new_lines)
