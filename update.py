import os, sys, shutil, zipfile, subprocess, tempfile, requests, logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Update")

BASE = os.path.dirname(os.path.abspath(__file__))
UPSTREAM_REPO = os.environ.get("UPSTREAM_REPO", "https://github.com/IamElite/ACB")
UPSTREAM_BRANCH = os.environ.get("UPSTREAM_BRANCH", "m1")
SKIP = {".git", "__pycache__", ".env", "update.py"}

def main():
    logger.info("Checking for updates...")
    clean = UPSTREAM_REPO.rstrip("/")
    if clean.endswith(".git"): clean = clean[:-4]
    zip_url = f"{clean}/archive/refs/heads/{UPSTREAM_BRANCH}.zip"
    try:
        with tempfile.TemporaryDirectory() as tmp:
            zip_path = os.path.join(tmp, "update.zip")
            ext_path = os.path.join(tmp, "extracted")
            os.makedirs(ext_path)
            r = requests.get(zip_url, stream=True, timeout=30)
            if r.status_code != 200:
                raise Exception(f"Download failed (HTTP {r.status_code})")
            with open(zip_path, "wb") as f:
                for chunk in r.iter_content(8192):
                    f.write(chunk)
            with zipfile.ZipFile(zip_path, "r") as z:
                z.extractall(ext_path)
            root = os.path.join(ext_path, os.listdir(ext_path)[0])
            for item in os.listdir(root):
                if item in SKIP: continue
                s = os.path.join(root, item)
                d = os.path.join(BASE, item)
                if os.path.exists(d):
                    (shutil.rmtree(d) if os.path.isdir(d) else os.remove(d))
                (shutil.move(s, d) if os.path.isdir(s) else shutil.move(s, d))
        req = os.path.join(BASE, "requirements.txt")
        if os.path.exists(req):
            logger.info("Installing dependencies...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", req, "--quiet"])
        logger.info("Update applied! Restarting bot...")
        
        # FIX: os.execl ki jagah os._exit(0) use kiya hai taaki Koyeb clean restart kare
        os._exit(0)
        
    except Exception as e:
        logger.error(f"Update failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
