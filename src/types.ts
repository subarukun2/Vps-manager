export interface PM2App {
  name: string;
  status: 'online' | 'stopped' | 'errored';
  cpu: number;
  memory: number;
  uptime: string;
  restarts: number;
}

export interface MetricPoint {
  time: string;
  cpu: number;
  ram: number;
  disk: number;
}
