# Add this debug statement in your settings.py
print("Session middleware settings:", {
    'SESSION_COOKIE_NAME': getattr(settings, 'SESSION_COOKIE_NAME', 'default'),
    'SESSION_COOKIE_SECURE': getattr(settings, 'SESSION_COOKIE_SECURE', 'default'),
    'SESSION_COOKIE_PATH': getattr(settings, 'SESSION_COOKIE_PATH', 'default'),
    'SESSION_SAVE_EVERY_REQUEST': getattr(settings, 'SESSION_SAVE_EVERY_REQUEST', 'default'),
}) 