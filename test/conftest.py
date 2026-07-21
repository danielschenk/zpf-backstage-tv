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


def pytest_addoption(parser):
    parser.addoption(
        "--docker-app",
        action="store_true",
        default=False,
        help="Run tests against Docker app instead of Python app"
    )


def pytest_configure(config):
    config.use_docker_app = config.getoption("--docker-app")


class SessionWithBaseUrl(requests.Session):
    def __init__(self, base_url):
        super().__init__()
        self.base_url = base_url

    def request(self, method, url, *args, **kwargs):
        joined_url = urllib.parse.urljoin(self.base_url, url)
        return super().request(method, joined_url, *args, **kwargs)


@pytest.fixture
def host(request):
    if request.config.use_docker_app:
        return "http://localhost:5001"
    return "http://localhost:5000"


@contextmanager
def _start_app_python(tmp_path: Path, virgin=False):
    """Start app using Python flask."""
    if not virgin:
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


@contextmanager
def _start_app_docker(tmp_path: Path, docker_image: str, virgin=False):
    """Start app using Docker container."""
    container_name = f"zpf-test-{os.getpid()}-{int(time.time() * 1000) % 1000000}"
    
    instance_data_dir = tmp_path / "instance_data"
    instance_data_dir.mkdir(exist_ok=True)
    
    if not virgin:
        shutil.copytree(INSTANCE_DIR, instance_data_dir, dirs_exist_ok=True)
    
    config_file = TEST_DIR / "settings.py"
    shutil.copy(config_file, instance_data_dir / "settings.py")
    
    os.chmod(instance_data_dir, 0o777)
    for root, dirs, files in os.walk(instance_data_dir):
        for d in dirs:
            os.chmod(os.path.join(root, d), 0o777)
        for f in files:
            os.chmod(os.path.join(root, f), 0o644)

    process = None
    try:
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

        process = subprocess.Popen(
            docker_run_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        
        time.sleep(2)
        
        if process.poll() is not None:
            stdout, stderr = process.communicate()
            raise RuntimeError(f"Docker container failed to start.\nStdout: {stdout}\nStderr: {stderr}")
        
        max_retries = 60
        for i in range(max_retries):
            try:
                response = requests.get("http://localhost:5001/login", timeout=2)
                if response.status_code == 200:
                    break
            except (requests.ConnectionError, requests.Timeout):
                if i == max_retries - 1:
                    try:
                        logs_output = subprocess.check_output(
                            ["docker", "logs", container_name],
                            timeout=5,
                            text=True,
                        )
                        print("Docker logs:", logs_output)
                    except subprocess.CalledProcessError as e:
                        print(f"Failed to get Docker logs: {e}")
                    raise RuntimeError(f"Failed to connect to app after {max_retries} retries")
                time.sleep(1)
        
        yield
    finally:
        if process is not None:
            try:
                subprocess.check_call(["docker", "stop", container_name], timeout=5)
            except subprocess.CalledProcessError:
                pytest.warning("Failed to stop Docker container")
            process.terminate()
            process.wait(timeout=5)


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


@pytest.fixture
def docker_image(request):
    """Get Docker image name from environment."""
    if not request.config.use_docker_app:
        return None
    
    docker_image = os.environ.get("DOCKER_IMAGE")
    
    if docker_image is None:
        raise pytest.UsageError("DOCKER_IMAGE environment variable must be set")
    
    return docker_image


@pytest.fixture
def app(tmp_path, request, docker_image):
    if request.config.use_docker_app:
        with _start_app_docker(tmp_path, docker_image):
            yield
    else:
        with _start_app_python(tmp_path):
            yield


@pytest.fixture
def app_virgin(tmp_path, request, docker_image):
    if request.config.use_docker_app:
        with _start_app_docker(tmp_path, docker_image, virgin=True):
            yield
    else:
        with _start_app_python(tmp_path, virgin=True):
            yield


@pytest.fixture
def session(host, app):
    return create_session(host)


@pytest.fixture
def session_virgin(host, app_virgin):
    return create_session(host)
