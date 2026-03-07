const express = require('express');
const router = express.Router();
const TriageReport = require('../models/TriageReport');
const TriageEngine = require('../utils/triageEngine');
const SeniorModel = require('../models/Senior');
const { URGENCY_LEVELS } = require('../config/constants');

// Input: { seniorId: 'SENIOR_001', text: 'Help I fell!' }
router.post('/triage', async (req, res) => {
  try {
    const { seniorId, text } = req.body;

    // 1. Validation
    if (!seniorId || !text) {
      return res.status(400).json({ error: 'Missing seniorId or text input' });
    }

    // 2. Get Profile
    const profile = SeniorModel.getProfileById(seniorId);
    if (!profile) {
      return res.status(404).json({ error: 'Senior profile not found' });
    }

    // 3. Process Audio -> Text
    const speechResult = await TriageEngine.processAudioToText(text);

    // 4. Calculate Urgency
    const urgencyAnalysis = await TriageEngine.calculateUrgencyScore(speechResult.transcript, seniorId);

    // 5. Define Action Based on Score
    let action = 'Monitor';
    if (urgencyAnalysis.score >= 5) action = 'Dispatch EMS Immediately';
    else if (urgencyAnalysis.score >= 3) action = 'Call Hotline Callback';

    // 6. Build Report
    const reportData = {
      seniorId,
      originalInput: text,
      processedText: speechResult.transcript,
      urgencyScore: urgencyAnalysis,
      recommendedAction: action,
      profileSnapshot: profile
    };

    const report = new TriageReport(reportData);

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

module.exports = router;
