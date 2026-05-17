#!/usr/bin/env python3
"""KAIROS — Entry point. Run with: uvicorn main:app --reload"""
from kairos.api.server import app

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("kairos.api.server:app", host="0.0.0.0", port=8000, reload=True)
