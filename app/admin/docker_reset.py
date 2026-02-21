import subprocess


def full_reset():

    print("[RESET] Stopping containers...")
    subprocess.run(["docker", "compose", "down"], check=True)

    print("[RESET] Removing volumes...")
    subprocess.run(["docker", "compose", "down", "-v"], check=True)

    print("[RESET] Recreating containers...")
    subprocess.run(["docker", "compose", "up", "-d"], check=True)

    print("[RESET] Full Docker reset complete.")
