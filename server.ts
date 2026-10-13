import express from 'express';
const app = express();
app.get('*', (req, res) => res.send('TeleVPS Backend Only Mode Active.'));
app.listen(3000);
