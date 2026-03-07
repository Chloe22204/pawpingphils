// src/utils/triageEngine.js
const { exec } = require('child_process');
const path = require('path');
const CONSTANTS = require('../config/constants');
const PROFILE_UTILS = require('../config/seniorProfiles');

/** 
 * NEW: Function to execute the external Python script 
 */
const transcribeAudio = async (filePath) => {
  return new Promise((resolve, reject) => {
    // Locate your python script relative to server.js
    const scriptPath = path.join(__dirname, '../../extract/whisper_test.py');
    
    // Command depends on your OS ('python' or 'python3')
    const pythonCommand = 'python'; 
    
    const command = `${pythonCommand} "${scriptPath}" --audio_path "${filePath}"`;

    console.log(`Running STT... ${command}`);

    exec(command, { timeout: 60000 }, (error, stdout, stderr) => {
      if (error) {
        return reject({ error: 'Python process failed', details: stderr });
      }

      try {
        // Parse the JSON output from Python
        const data = JSON.parse(stdout);
        
        // Check for error returned by Python
        if(data.error) {
          return reject({ error: 'Whisper Error', details: data.error });
        }

        resolve(data);
      } catch (parseErr) {
        reject({ error: 'Failed to parse output', details: stdout });
      }
    });
  });
};

// Keep your existing calculateUrgencyScore function here 
// (Assuming you kept it from the previous setup)
const calculateUrgencyScore = async (text, seniorId) => {
   // ... [Paste your existing urgency logic here] ...
   // Ensure you have access to CONSTANTS and PROFILE_UTILS
   const profile = PROFILE_UTILS.SENIOR_DB[seniorId] || null;
   let currentScore = 2; 
   const lowerText = text.toLowerCase();

   CONSTANTS.KEYWORDS.forEach(item => {
     if (lowerText.includes(item.term)) {
       currentScore += item.weight;
     }
   });

   // Clamp score
   let finalScore = Math.min(Math.max(currentScore, 1), 5);

   return {
     score: finalScore,
     level: CONSTANTS.URGENCY_LEVELS.HIGH.label === 'Critical' ? 'Critical' : 'Normal', // Simplified for example
     detectedTerms: [] 
   };
};

module.exports = { transcribeAudio, calculateUrgencyScore };
