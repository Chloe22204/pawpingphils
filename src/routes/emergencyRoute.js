const express = require('express');
const router = express.Router();
const multer = require('multer');
const fs = require('fs');
const TriageReport = require('../models/TriageReport');
const EngineUtils = require('../utils/triageEngine'); // Updated utils import
const SeniorModel = require('../models/Senior');

// Configure Multer for temporary file storage
const upload = multer({ dest: 'uploads/' }); 

// Define Action Logic helper
const determineAction = (score) => {
  if (score >= 5) return 'Dispatch EMS Immediately';
  if (score >= 3) return 'Call Hotline Callback';
  return 'Schedule Follow-up';
};

// UPDATED ROUTE: Accepts FILE instead of Text
router.post('/triage/upload', upload.single('audio'), async (req, res) => {
  try {
    // 1. Validation
    if (!req.file || !req.body.seniorId) {
      return res.status(400).json({ error: 'Missing audio file or senior ID' });
    }

    const filePath = req.file.path; // Temporary path Node.js stored the file
    const seniorId = req.body.seniorId;

    // 2. Validate Senior Profile
    const profile = SeniorModel.getProfileById(seniorId);
    if (!profile) {
      return res.status(404).json({ error: 'Senior profile not found' });
    }

    console.log(`Processing Audio: ${filePath}`);

    // 3. Call Python Whisper Model
    const sttResult = await EngineUtils.transcribeAudio(filePath);

    // 4. Calculate Urgency based on Transcript
    const urgencyData = await EngineUtils.calculateUrgencyScore(sttResult.transcript, seniorId);

    // 5. Prepare Final Response
    const report = {
      timestamp: new Date().toISOString(),
      seniorId: seniorId,
      fileName: req.file.originalname,
      language: sttResult.language,
      originalTranscript: sttResult.transcript,
      urgencyScore: urgencyData.score,
      urgencyLevel: urgencyData.level || 'Low',
      recommendedAction: determineAction(urgencyData.score),
      profileSnapshot: profile
    };

    // 6. Cleanup Temp File (Optional but recommended)
    setTimeout(() => {
        if(fs.existsSync(filePath)){
            fs.unlinkSync(filePath);
        }
    }, 60000);

    return res.status(200).json(report);

  } catch (error) {
    console.error('Error in /triage/upload:', error);
    return res.status(500).json({ error: 'System processing error', details: error.message });
  }
});

module.exports = router;

