import asyncio
from unittest.mock import patch

import pytest

from app.core.config import Settings
from app.main import create_app


def test_engine_is_disposed_even_when_lifespan_exits_with_an_error(engine):
    app = create_app(Settings(_env_file=None, app_env="test"), engine)

    async def fail_during_lifespan():
        async with app.router.lifespan_context(app):
            raise RuntimeError("Simulated shutdown error")

    with patch.object(engine, "dispose") as dispose:
        with pytest.raises(RuntimeError, match="Simulated shutdown error"):
            asyncio.run(fail_during_lifespan())
        dispose.assert_called_once()
