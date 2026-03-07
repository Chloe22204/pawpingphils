const { SENIOR_DB } = require('../config/seniorProfiles');

const getProfileById = (id) => {
  return SENIOR_DB[id];
};

module.exports = { getProfileById };
