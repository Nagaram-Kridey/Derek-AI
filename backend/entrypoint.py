"""Container bootstrap: load AWS secrets using instance IAM, then run a fixed role."""
import json
import os
import sys
import subprocess
from urllib.parse import quote

def load_secrets():
    if not os.getenv("LILYLEO_SECRET_ARN"):
        return
    import boto3
    client = boto3.client("secretsmanager", region_name=os.getenv("AWS_REGION", "ap-south-1"))
    def get(arn):
        return json.loads(client.get_secret_value(SecretId=arn)["SecretString"])
    allowed = {"DJANGO_SECRET_KEY", "GEMINI_API_KEY", "GEMINI_MODEL", "CREDENTIAL_ENCRYPTION_KEY", "GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GOOGLE_REDIRECT_URI", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "TELEGRAM_WEBHOOK_SECRET", "CARTESIA_API_KEY", "CARTESIA_VOICE_ID", "CARTESIA_API_VERSION", "CARTESIA_MODEL", "SEMANTIC_SCHOLAR_API_KEY", "DAILY_MODEL_CALL_LIMIT", "DAILY_INPUT_CHAR_LIMIT", "WHISPER_MODEL"}
    for key, value in get(os.environ["LILYLEO_SECRET_ARN"]).items():
        if key in allowed and isinstance(value, (str, int)):
            os.environ[key] = str(value)
    db = get(os.environ["DATABASE_SECRET_ARN"])
    os.environ["DATABASE_URL"] = f"postgresql://{quote(db['username'], safe='')}:{quote(db['password'], safe='')}@{os.environ['DATABASE_HOST']}:5432/lilyleo?sslmode=require"
    redis = get(os.environ["REDIS_SECRET_ARN"])
    os.environ["REDIS_URL"] = f"rediss://:{quote(redis['password'], safe='')}@{os.environ['REDIS_HOST']}:6379/0?ssl_cert_reqs=required"

if __name__ == "__main__":
    load_secrets()
    if os.getenv("RUN_MIGRATIONS", "false").lower() == "true":
        subprocess.run([sys.executable, "/app/backend/manage.py", "migrate", "--noinput"], check=True)
    if len(sys.argv) < 2:
        raise SystemExit("Specify a container command")
    os.execvp(sys.argv[1], sys.argv[1:])
