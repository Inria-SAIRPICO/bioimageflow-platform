import type { File, Task } from '@vitest/runner'
import { updateTask } from '@vitest/runner'
import { getTests } from '@vitest/runner/utils'
import { VitestTestRunner } from 'vitest/runners'
import { includesTest, readTestSuite } from '../src/test-utils/testSuite'

/** Apply feature selection before suite hooks and test callbacks execute. */
export function selectTasks(tasks: Task[], suite = readTestSuite()): void {
  for (const task of tasks) {
    if (task.type === 'suite') {
      selectTasks(task.tasks, suite)
      if (task.tasks.length && task.tasks.every(child => child.mode === 'skip' || child.mode === 'todo')) {
        task.mode = 'skip'
      }
    } else if (!includesTest(suite, /@distributed\b/.test(task.name))) {
      task.mode = 'skip'
    }
  }
}

export default class FeatureSuiteRunner extends VitestTestRunner {
  onCollected(files: File[]): void {
    selectTasks(files)
    // Entirely skipped suites do not visit their children during execution.
    // Publish those results explicitly so reports count every excluded case.
    for (const test of getTests(files)) {
      if (test.mode === 'skip') {
        test.result = { state: 'skip' }
        updateTask('test-finished', test, this)
      }
    }
  }
}
