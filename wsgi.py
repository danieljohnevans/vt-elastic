import sys
import subprocess
import os

# Set the path for your application
path = '/var/www/webroot/ROOT'
if path not in sys.path:
    sys.path.append(path)

# Step 1: Install dependencies from requirements.txt
def install_requirements():
    requirements_path = os.path.join(path, 'requirements.txt')
    if os.path.exists(requirements_path):
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", requirements_path])
            print("Requirements installed successfully.")
        except subprocess.CalledProcessError as e:
            print(f"Failed to install requirements: {e}")
            sys.exit(1)
    else:
        print(f"requirements.txt not found at {requirements_path}")

# Step 2: Run the entrypoint.sh script (which starts Gunicorn)
def run_entrypoint():
    entrypoint_path = os.path.join(path, 'entrypoint.sh')
    if os.path.exists(entrypoint_path):
        try:
            subprocess.check_call(["/bin/sh", entrypoint_path])
            print("entrypoint.sh executed successfully.")
        except subprocess.CalledProcessError as e:
            print(f"Failed to execute entrypoint.sh: {e}")
            sys.exit(1)
    else:
        print(f"entrypoint.sh not found at {entrypoint_path}")

# Main execution
if __name__ == "__main__":
    # Install the dependencies
    install_requirements()

    # Run the entrypoint.sh script
    run_entrypoint()

# Import the Flask application
from app import app
application = app