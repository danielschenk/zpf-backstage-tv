"""Common fixtures"""

import subprocess
from contextlib import contextmanager
from pathlib import Path
import shutil
import time
import os

import pytest
import requests
import urllib.parse
import bs4


TEST_DIR = Path(__file__).parent
INSTANCE_DIR = TEST_DIR / "instance"
ROOT_DIR = TEST_DIR.parent


class SessionWithBaseUrl(requests.Session):
    def __init__(self, base_url):
        super().__init__()
        self.base_url = base_url

    def request(self, method, url, *args, **kwargs):
        joined_url = urllib.parse.urljoin(self.base_url, url)
        return super().request(method, joined_url, *args, **kwargs)


@pytest.fixture
def host():
    return "http://localhost:5000"


@pytest.fixture
def session(host, app):
    return create_session(host)


@pytest.fixture
def session_virgin(host, app_virgin):
    return create_session(host)


def create_session(host):
    session = SessionWithBaseUrl(host)

    response = session.get("/login")
    soup = bs4.BeautifulSoup(response.text, "html.parser")
    csrf_input = soup.find("input", {"id": "csrf_token"})

    data = {
        "csrf_token": csrf_input.attrs["value"],
        "username": "test",
        "password": "test",
        "submit": "Submit",
    }
    headers = {"Upgrade-Insecure-Requests": "1"}
    response = session.post("/login", data=data, headers=headers)
    assert response.history[0].headers["Location"] == "/"

    return session


@contextmanager
def app_process(tmp_path: Path, virgin=False):
    if not virgin:
        # copy instance data to a tempdir, so that we always start app with same state
        shutil.copytree(INSTANCE_DIR, tmp_path, dirs_exist_ok=True)

    config = (TEST_DIR / "settings.py").absolute()
    with subprocess.Popen(
        [
            "flask",
            "--app",
            f'app:create_app(instance_path="{str(tmp_path)}",config_filename="{str(config)}")',
            "run",
        ],
        cwd=ROOT_DIR,
    ) as p:
        time.sleep(3)
        assert p.poll() is None
        yield
        p.kill()


@pytest.fixture
def app(tmp_path):
    with app_process(tmp_path):
        yield


@pytest.fixture
def app_virgin(tmp_path):
    with app_process(tmp_path, virgin=True):
        yield


@contextmanager
def docker_app_container(tmp_path: Path, docker_image: str, virgin=False):
    """Start a Docker container with the app for testing."""
    container_name = f"zpf-test-{os.getpid()}-{int(time.time() * 1000) % 1000000}"
    
    # Prepare instance data
    instance_data_dir = tmp_path / "instance_data"
    instance_data_dir.mkdir(exist_ok=True)
    
    if not virgin:
        shutil.copytree(INSTANCE_DIR, instance_data_dir, dirs_exist_ok=True)
    
    # Copy settings file to the instance data directory
    config_file = TEST_DIR / "settings.py"
    shutil.copy(config_file, instance_data_dir / "settings.py")
    
    # Make the directory readable by everyone (to avoid permission issues in container)
    os.chmod(instance_data_dir, 0o777)
    for root, dirs, files in os.walk(instance_data_dir):
        for d in dirs:
            os.chmod(os.path.join(root, d), 0o777)
        for f in files:
            os.chmod(os.path.join(root, f), 0o644)

    process = None
    try:
        # Run Docker container
        # Mount the test instance data at /instance (the default location in the container)
        docker_run_cmd = [
            "docker",
            "run",
            "--rm",
            "--name",
            container_name,
            "-p",
            "5001:8080",
            "-e",
            "HOST=0.0.0.0",
            "-v",
            f"{instance_data_dir}:/instance",
            docker_image,
        ]

        # Start container - use a separate thread to handle subprocess
        process = subprocess.Popen(
            docker_run_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        
        # Give the container a moment to start
        time.sleep(2)
        
        # Check if process failed immediately
        if process.poll() is not None:
            stdout, stderr = process.communicate()
            raise RuntimeError(f"Docker container failed to start.\nStdout: {stdout}\nStderr: {stderr}")
        
        # Wait for container to be ready
        max_retries = 60
        for i in range(max_retries):
            try:
                response = requests.get("http://localhost:5001/login", timeout=2)
                if response.status_code == 200:
                    break
            except (requests.ConnectionError, requests.Timeout):
                if i == max_retries - 1:
                    # Get container logs for debugging
                    try:
                        logs_cmd = ["docker", "logs", container_name]
                        logs_result = subprocess.run(logs_cmd, capture_output=True, text=True, timeout=5)
                        print("Docker logs:", logs_result.stdout)
                        print("Docker errors:", logs_result.stderr)
                    except Exception as e:
                        print(f"Failed to get Docker logs: {e}")
                    raise RuntimeError(f"Failed to connect to app after {max_retries} retries")
                time.sleep(1)
        
        yield
    finally:
        # Clean up
        if process is not None:
            try:
                subprocess.run(["docker", "stop", container_name], timeout=5)
            except Exception:
                pass
            try:
                process.terminate()
                process.wait(timeout=5)
            except Exception:
                pass


@pytest.fixture
def docker_image():
    """Get Docker image name from environment or use default."""
    return os.environ.get("DOCKER_IMAGE", "zpf-backstage-tv:latest")


@pytest.fixture
def host_docker():
    return "http://localhost:5001"


@pytest.fixture
def session_docker(host_docker, app_docker):
    return create_session(host_docker)


@pytest.fixture
def session_docker_virgin(host_docker, app_docker_virgin):
    return create_session(host_docker)


@pytest.fixture
def app_docker(tmp_path, docker_image):
    with docker_app_container(tmp_path, docker_image):
        yield


@pytest.fixture
def app_docker_virgin(tmp_path, docker_image):
    with docker_app_container(tmp_path, docker_image, virgin=True):
        yield
