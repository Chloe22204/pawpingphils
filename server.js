require('dotenv').config();
const express = require('express');
const bodyParser = require('body-parser');
const cors = require('cors');

const emergencyRoute = require('./src/routes/emergencyRoute');
const port = process.env.PORT || 3000;

const app = express();

// Middleware
app.use(cors());
app.use(bodyParser.json());
app.use(express.urlencoded({ extended: true }));

// Logging
app.use((req, res, next) => {
  console.log(`[${new Date().toISOString()}] ${req.method} ${req.path}`);
  next();
});

// Routes
app.use('/api/v1/emergency', emergencyRoute);

// Root check
app.get('/', (req, res) => {
  res.json({ 
    status: 'Online', 
    service: 'Senior Emergency Triage Backend',
    endPoints: ['/api/v1/emergency/triage'] 
  });
});

// Start Server
app.listen(port, () => {
  console.log(`Server running on http://localhost:${port}`);
});
