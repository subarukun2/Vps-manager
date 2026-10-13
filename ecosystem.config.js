module.exports = {
  apps: [
    {
      name: "televps-bot",
      script: "./venv/bin/python",
      args: "bot.py",
      autorestart: true,
      watch: false,
      log_date_format: "YYYY-MM-DD HH:mm:ss",
      env: {
        PYTHONUNBUFFERED: "1"
      }
    },
    {
      name: "televps-webhook",
      script: "./venv/bin/uvicorn",
      args: "webhook:app --host 0.0.0.0 --port 8080",
      autorestart: true,
      watch: false,
      log_date_format: "YYYY-MM-DD HH:mm:ss"
    }
  ]
};
