const shared = {
  paths: ['spec/features/**/*.feature'],
  requireModule: ['tsx/cjs'],
  require: ['steps/**/*.ts'],
};

module.exports = {
  default: { ...shared, tags: 'not @real-agent' },
  real: { ...shared, tags: '@real-agent' },
};
