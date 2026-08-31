// Jest设置文件
// 配置测试环境

// 模拟浏览器环境
global.document = require('jest-environment-jsdom');
global.window = document.defaultView;
global.navigator = window.navigator;

// 模拟本地存储
const localStorageMock = {
  getItem: jest.fn(),
  setItem: jest.fn(),
  removeItem: jest.fn(),
  clear: jest.fn()
};
global.localStorage = localStorageMock;

// 模拟fetch API
global.fetch = jest.fn(() =>
  Promise.resolve({
    json: () => Promise.resolve({}),
    ok: true
  })
);

// 设置测试超时
jest.setTimeout(10000);

// 模拟控制台输出
const originalConsole = console;
const mockConsole = {
  log: jest.fn(),
  warn: jest.fn(),
  error: jest.fn(),
  info: jest.fn(),
  debug: jest.fn()
};

// 在测试前设置模拟控制台
beforeAll(() => {
  global.console = mockConsole;
});

// 测试后恢复原始控制台
afterAll(() => {
  global.console = originalConsole;
});