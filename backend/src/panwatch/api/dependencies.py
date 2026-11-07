from __future__ import annotations

from fastapi import Request


def get_session(request: Request):
    session = request.app.state.session_factory()
    try:
        yield session
    finally:
        session.close()

