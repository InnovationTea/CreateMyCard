import { describe, beforeAll, beforeEach, afterEach, afterAll, it, expect } from '@ohos/hypium';
import { isSafeSampleFile, isValidContainerSize, normalizeDimension, parseA2UIMessages } from '../main/ets/runner/A2UIProtocol';

export default function localUnitTest() {
  describe('localUnitTest', () => {
    // Defines a test suite. Two parameters are supported: test suite name and test suite function.
    beforeAll(() => {
      // Presets an action, which is performed only once before all test cases of the test suite start.
      // This API supports only one parameter: preset action function.
    });
    beforeEach(() => {
      // Presets an action, which is performed before each unit test case starts.
      // The number of execution times is the same as the number of test cases defined by **it**.
      // This API supports only one parameter: preset action function.
    });
    afterEach(() => {
      // Presets a clear action, which is performed after each unit test case ends.
      // The number of execution times is the same as the number of test cases defined by **it**.
      // This API supports only one parameter: clear action function.
    });
    afterAll(() => {
      // Presets a clear action, which is performed after all test cases of the test suite end.
      // This API supports only one parameter: clear action function.
    });
    it('assertContain', 0, () => {
      // Defines a test case. This API supports three parameters: test case name, filter parameter, and test case function.
      let a = 'abc';
      let b = 'b';
      // Defines a variety of assertion methods, which are used to declare expected boolean conditions.
      expect(a).assertContain(b);
      expect(a).assertEqual(a);
    });
    it('parseDocumentAndJsonLines', 0, () => {
      expect(parseA2UIMessages('{"version":"v0.9","createSurface":{}}').length).assertEqual(1);
      expect(parseA2UIMessages('[{"a":1},{"b":2}]').length).assertEqual(2);
      expect(parseA2UIMessages('{"a":1}\n{"b":2}').length).assertEqual(2);
    });
    it('validateSampleFile', 0, () => {
      expect(isSafeSampleFile('current.json')).assertTrue();
      expect(isSafeSampleFile('../current.json')).assertFalse();
      expect(isSafeSampleFile('/data/current.json')).assertFalse();
    });
    it('validateContainerSize', 0, () => {
      expect(isValidContainerSize(150, 150, 360, 640)).assertTrue();
      expect(isValidContainerSize(400, 150, 360, 640)).assertFalse();
      expect(isValidContainerSize(0, 150, 360, 640)).assertFalse();
      expect(normalizeDimension(undefined, 150)).assertEqual(150);
      expect(normalizeDimension(0, 150)).assertEqual(0);
    });
  });
}
