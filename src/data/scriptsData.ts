export const SCRIPTS_DATA = {
  'bot.py': {
    name: 'bot.py',
    description: 'The core Telegram Bot orchestrator using python-telegram-bot and PyGithub.',
    language: 'python'
  },
  'webhook.py': {
    name: 'webhook.py',
    description: 'FastAPI server for handling GitHub webhooks and triggering auto-deployments.',
    language: 'python'
  },
  'setup.sh': {
    name: 'setup.sh',
    description: 'The 1-click magic installer for Ubuntu 22.04 LTS.',
    language: 'bash'
  },
  'ecosystem.config.js': {
    name: 'ecosystem.config.js',
    description: 'PM2 configuration for managing the bot and webhook processes.',
    language: 'javascript'
  },
  'requirements.txt': {
    name: 'requirements.txt',
    description: 'Python dependencies for the TeleVPS system.',
    language: 'text'
  }
};
