const multer = require('multer');
const path = require('path');
const upload = multer({ dest: 'uploads/' });

const express = require('express');
const router = express.Router();
const TriageReport = require('../models/TriageReport');
const TriageEngine = require('../utils/triageEngine');
const SeniorModel = require('../models/Senior');
const { URGENCY_LEVELS } = require('../config/constants');

// Input: { seniorId: 'SENIOR_001', text: 'Help I fell!' }
// Change '/triage' to '/triage/upload' or handle multipart forms
router.post('/triage/upload', upload.single('audio'), async (req, res) => {
  try {
    // 1. Validate Input
    if (!req.file || !req.body.seniorId) {
      return res.status(400).json({ error: 'Missing audio file or senior ID' });
    }

    // 2. Get Profile
    const profile = SeniorModel.getProfileById(req.body.seniorId);
    if (!profile) {
      return res.status(404).json({ error: 'Senior profile not found' });
    }

    // 3. Transcribe Audio (Call Python)
    const speechResult = await TriageEngine.processAudioToText(req.file.path);
    
    // NOTE: req.file.path now contains the temporary stored file location

    // 4. Calculate Urgency (Pass transcript)
    const urgencyAnalysis = await TriageEngine.calculateUrgencyScore(speechResult.transcript, req.body.seniorId);

    // 5. Define Action
    let action = 'Monitor';
    if (urgencyAnalysis.score >= 5) action = 'Dispatch EMS Immediately';
    else if (urgencyAnalysis.score >= 3) action = 'Call Hotline Callback';

    // 6. Build Report
    const reportData = {
      seniorId: req.body.seniorId,
      originalInput: speechResult.transcript, // Speech result replaces text input
      processedText: speechResult.transcript,
      language: speechResult.language,
      urgencyScore: urgencyAnalysis,
      recommendedAction: action,
      healthProfileSnapshot: profile
    };

    const report = new TriageReport(reportData);

    // Optional: Clean up temp file after processing
    // fs.unlinkSync(req.file.path); 

    return res.status(200).json({
      success: true,
      message: 'Emergency analysis complete',
      ...report
    });

  } catch (error) {
    console.error(error);
    return res.status(500).json({ error: 'Internal Server Error', details: error.message });
  }
});
