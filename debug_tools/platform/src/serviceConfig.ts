export const SERVICE_CONFIG_GROUPS = [
  {
    title: '模型路由',
    keys: [
      'enableA2uiModelMock', 'designCompactModelBackend', 'openaiMasterClient',
      'openaiFallbackClient', 'deepseekOfficialHttpModel',
      'deepseekOfficialHttpTemperature', 'deepseekOfficialHttpTopP',
      'deepseekOfficialHttpMaxTokens', 'deepseekOfficialHttpEnableThinking',
    ],
  },
  {
    title: '失败处理',
    keys: [
      'enableModelFailureRetry', 'modelFailureMaxRetryAttempts',
      'fallbackModelFailureMaxRetryAttempts', 'enableOpenaiFallback',
      'enableValidationFailureRetry', 'validationFailureMaxRepairAttempts',
      'enableCompactDslInterfaceRetry', 'compactDslInterfaceRetryCount',
    ],
  },
] as const;

export function serviceConfigLabel(key: string): string {
  return key.replace(/([A-Z])/g, ' $1').replace(/^./, (value) => value.toUpperCase());
}
