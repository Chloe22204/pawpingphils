module.exports = {
  URGENCY_LEVELS: {
    LOW: { min: 1, max: 2, label: 'Routine' },
    MEDIUM: { min: 3, max: 4, label: 'Urgent' },
    HIGH: { min: 5, max: 5, label: 'Critical' }
  },
  KEYWORDS: [
    { term: 'fall', weight: 5, category: 'trauma' },
    { term: 'fallen', weight: 5, category: 'trauma' },
    { term: 'chest pain', weight: 6, category: 'cardiac' },
    { term: 'heart attack', weight: 7, category: 'cardiac' },
    { term: 'stroke', weight: 6, category: 'neurological' },
    { term: 'shortness of breath', weight: 5, category: 'respiratory' },
    { term: 'help', weight: 2, category: 'general' },
    { term: 'can breathe', weight: -1, category: 'general' }, // Negative score helps reduce urgency if negated
  ],
  SCORE_MAX: 5
};
