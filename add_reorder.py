file_path = 'kairos/api/routes/web.py'
with open(file_path, 'r') as f:
    lines = f.readlines()

insert_idx = -1
for i, line in enumerate(lines):
    if '@router.put("/api/v1/journeys/{phase_id}/phases")' in line:
        # Find the end of this function
        curr = i + 1
        while curr < len(lines) and (lines[curr].startswith(' ') or lines[curr].strip() == ''):
            curr += 1
        insert_idx = curr
        break

if insert_idx != -1:
    new_handler = [
        '\n',
        '@router.put("/api/v1/journeys/phases/{phase_id}/reorder")\n',
        'async def reorder_phase_web(req: Request, phase_id: str):\n',
        '    coach = await _get_coach(req)\n',
        '    if not coach: return JSONResponse({"ok": False}, status_code=403)\n',
        '    body = await req.json()\n',
        '    je = req.app.state.journey_engine\n',
        '    ok = await je.reorder_phase(phase_id, direction=body.get("direction", "up"))\n',
        '    return {"ok": ok}\n'
    ]
    lines[insert_idx:insert_idx] = new_handler
    with open(file_path, 'w') as f:
        f.writelines(lines)
    print('Handler inserted successfully')
else:
    print('Could not find insertion point')
