from libretranslate import main
import sys

# Set WSGI mode
sys.argv = ['--wsgi']

# Create the application instance
application = main()

# For backwards compatibility, also provide 'app'
app = application

# For ASGI compatibility (uvicorn.workers.UvicornWorker)
def create_asgi_app():
    """Create ASGI application by wrapping the WSGI app"""
    try:
        from asgiref.wsgi import WsgiToAsgi
        return WsgiToAsgi(application)
    except ImportError:
        # If asgiref is not available, fall back to WSGI
        return application

# ASGI application for uvicorn
asgi_application = create_asgi_app()
