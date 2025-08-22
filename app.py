#!/usr/bin/env python3
"""
Main application file for the Flask Deployer.
This is a compatibility wrapper that imports the restructured application.
"""

import os
import sys
from pathlib import Path

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent))

from deployer import create_app
from deployer.services.process_service import ProcessService, setup_signal_handlers

# Create the application
app = create_app()

if __name__ == '__main__':
    # Setup signal handlers for graceful shutdown
    try:
        process_service = ProcessService.get_instance()
        setup_signal_handlers(process_service)
    except Exception as e:
        print(f"Warning: Could not setup signal handlers: {e}")
    
    # Get configuration from environment variables
    from deployer.utils.env_config import get_server_config
    server_config = get_server_config()
    host = server_config['HOST']
    port = server_config['PORT']
    debug = server_config['DEBUG']
    
    print(f"Starting Deployer on http://{host}:{port}")
    print(f"Debug mode: {debug}")
    print(f"Vault path: {app.config['VAULT_PATH']}")
    print("🚀 Using WebSockets for real-time logs")
    
    # Run the SocketIO application
    app.socketio.run(
        app,
        host=host,
        port=port,
        debug=debug,
        use_reloader=debug,
        allow_unsafe_werkzeug=True
    )