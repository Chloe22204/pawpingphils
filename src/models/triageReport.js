class TriageReport {
  constructor(data) {
    this.timestamp = new Date().toISOString();
    this.seniorId = data.seniorId;
    this.originalInput = data.originalInput;
    this.processedText = data.processedText;
    this.urgencyScore = data.urgencyScore.score;
    this.urgencyLabel = data.urgencyScore.level;
    this.recommendedAction = data.recommendedAction;
    this.healthProfileSnapshot = data.profileSnapshot;
  }
}

module.exports = TriageReport;
