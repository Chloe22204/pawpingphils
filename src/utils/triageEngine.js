const { exec } = require('child_process');
const path = require('path');
const CONSTANTS = require('../config/constants');
const PROFILE_UTILS = require('../config/seniorProfiles');

/**
 * Calls the external Python STT Service
 */
const processAudioToText = async (filePath) => {
  return new Promise((resolve, reject) => {
    const pythonPath = 'python'; // or 'python3' on Mac/Linux
    const scriptPath = path.join(__dirname, '../../python-stt/transcribe.py');
    
    const command = `${pythonPath} "${scriptPath}" --audio_path "${filePath}"`;

    console.log(`Executing STT: ${command}`);

    exec(command, { timeout: 60000 }, (error, stdout, stderr) => {
      if (error) {
        console.error(`STT Error: ${error.message}`);
        return reject({ error: 'Transcription failed', details: stderr });
      }

      try {
        // Parse the JSON string output from Python
        const data = JSON.parse(stdout);
        resolve(data);
      } catch (parseErr) {
        reject({ error: 'Failed to parse STT output', details: stdout });
      }
    });
  });
};

// ... Rest of calculateUrgencyScore remains the same ...
const calculateUrgencyScore = async (text, seniorId) => {
  // Logic stays identical
  const profile = PROFILE_UTILS.SENIOR_DB[seniorId] || null;
  let currentScore = 2; 
  const lowerText = text.toLowerCase();
  
  CONSTANTS.KEYWORDS.forEach(item => {
    if (lowerText.includes(item.term)) {
      currentScore += item.weight;
    }
  });
  
  if (profile && profile.conditions.includes('Arrhythmia')) {
    if (lowerText.includes('chest') || lowerText.includes('heart')) {
      currentScore += 1; 
    }
  }

  let finalScore = Math.min(Math.max(currentScore, 1), CONSTANTS.SCORE_MAX);

  return {
    score: finalScore,
    level: Object.values(CONSTANTS.URGENCY_LEVELS).find(l => 
      finalScore >= l.min && finalScore <= l.max
    ).label,
    detectedTerms: CONSTANTS.KEYWORDS.filter(k => 
      lowerText.includes(k.term)
    ).map(k => k.category)
  };
};

module.exports = { processAudioToText, calculateUrgencyScore };
