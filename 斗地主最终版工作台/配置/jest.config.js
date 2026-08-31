// Jest配置文件
// 用于前端JavaScript测试

module.exports = {
  // 测试环境
  testEnvironment: 'jsdom',
  
  // 测试文件匹配规则
  testMatch: [
    '**/测试用例/**/*.test.js',
    '**/测试用例/**/*.spec.js'
  ],
  
  // 覆盖率配置
  collectCoverage: true,
  coverageDirectory: 'coverage',
  coverageReporters: ['text', 'lcov', 'html'],
  
  // 覆盖率阈值
  coverageThreshold: {
    global: {
      branches: 80,
      functions: 80,
      lines: 80,
      statements: 80
    }
  },
  
  // 模块名映射
  moduleNameMapper: {
    '^@/(.*)$': '<rootDir>/$1'
  },
  
  // 设置文件
  setupFiles: ['<rootDir>/配置/jest.setup.js'],
  
  // 测试超时时间
  testTimeout: 10000,
  
  // 详细输出
  verbose: true
};