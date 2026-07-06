from core.logger import get_logger

# 统一业务 logger 入口。业务代码统一使用 `from app.logger import logger`。
logger = get_logger("genui-agent-service")
