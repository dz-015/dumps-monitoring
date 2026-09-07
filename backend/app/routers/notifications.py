"""Подключение каналов уведомлений: Telegram и МАКС."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db.database import get_db
from app.db.models import User
from app.notify import deep_link, max_deep_link, max_enabled, telegram_enabled
from app.schemas import TelegramStatus

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("/telegram", response_model=TelegramStatus)
def telegram_status(current_user: User = Depends(get_current_user)):
    """Состояние привязки + свежая deep-link «Подключить».

    Ссылка живёт час (внутри подписанный токен) — фронт запрашивает её в момент
    открытия профиля, а не хранит.
    """
    return TelegramStatus(
        enabled=telegram_enabled(),
        connected=current_user.telegram_connected,
        link=deep_link(current_user.id) if telegram_enabled() else None,
    )


@router.delete("/telegram", response_model=TelegramStatus)
def telegram_disconnect(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    current_user.telegram_chat_id = None
    db.commit()
    return TelegramStatus(
        enabled=telegram_enabled(),
        connected=False,
        link=deep_link(current_user.id) if telegram_enabled() else None,
    )


# Статус и отвязка МАКС — та же схема ответа, что у Telegram: обе строки
# профиля рисуются одним компонентом.

@router.get("/max", response_model=TelegramStatus)
def max_status(current_user: User = Depends(get_current_user)):
    return TelegramStatus(
        enabled=max_enabled(),
        connected=current_user.max_connected,
        link=max_deep_link(current_user.id) if max_enabled() else None,
    )


@router.delete("/max", response_model=TelegramStatus)
def max_disconnect(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    current_user.max_user_id = None
    db.commit()
    return TelegramStatus(
        enabled=max_enabled(),
        connected=False,
        link=max_deep_link(current_user.id) if max_enabled() else None,
    )
