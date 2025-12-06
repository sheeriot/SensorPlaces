from ..models import Place
from ..services.switchbot_service import SwitchBotService

def get_switchbot_service_from_place(place: Place) -> SwitchBotService:
    """
    Initializes and returns a SwitchBotService instance for a given Place.
    """
    if not place.switchbot_enable or not place.switchbot_token or not place.switchbot_secret:
        raise Exception("SwitchBot integration is not fully configured for this place.")
    
    return SwitchBotService(place=place)
