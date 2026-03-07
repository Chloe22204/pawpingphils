const CONSTANTS = require('../config/constants');
const PROFILE_UTILS = require('../config/seniorProfiles');

/**
 * Simulates Speech-to-Text and Translation.
 * In production, send raw audio buffer to Google/AWS STT API here.
 */
const processAudioToText = async (audioInput) => {
  return new Promise((resolve) => {
    setTimeout(() => {
      resolve({
        transcript: audioInput || "I fell down", // Simulated output
        language: audioInput.includes('estoy') ? 'Spanish' : 'English',
        confidence: 0.95
      });
    }, 500);
  });
};

/**
 * Calculates urgency score based on text and profile.
 */
const calculateUrgencyScore = async (text, seniorId) => {
  const profile = PROFILE_UTILS.SENIOR_DB[seniorId] || null;
  let currentScore = 2; // Base score

  // 1. Keyword Analysis
  const lowerText = text.toLowerCase();
  
  CONSTANTS.KEYWORDS.forEach(item => {
    if (lowerText.includes(item.term)) {
      currentScore += item.weight;
    }
  });

  // 2. Profile Context Adjustment
  if (profile && profile.conditions.includes('Arrhythmia')) {
    if (lowerText.includes('chest') || lowerText.includes('heart')) {
      currentScore += 1; // Extra risk factor
    }
  }

  // 3. Clamping Score
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
