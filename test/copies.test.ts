// The copy check's chrF must agree with sacrebleu's sentence chrF, or its
// threshold of 90 means something other than it does in published chrF
// scores. The expected values were computed with sacrebleu 2.x, CHRF() defaults.
import { describe, expect, test } from 'bun:test'
import { chrf, isCopy } from '../copies'

describe('chrF, as sacrebleu computes it', () => {
  test('a near copy and an independent translation of the same Assamese sentence', () => {
    const pib = 'বিমানৰ ৰক্ষণাবেক্ষণ, মেৰামতি আৰু অভাৰহ’ল খণ্ডত ভাৰতে এই বৃহৎ পদক্ষেপ গ্ৰহণ কৰিছে।'
    const google = 'বিমান ৰক্ষণাবেক্ষণ, মেৰামতি, আৰু অভাৰহ’ল খণ্ডত ভাৰতে এই বৃহৎ পদক্ষেপ গ্ৰহণ কৰিছে।'
    const sarvam = 'ভাৰতে বিমান ৰক্ষণাবেক্ষণ, মেৰামতি আৰু অভাৰহল (MRO) খণ্ডত এই গুৰুত্বপূৰ্ণ পদক্ষেপ গ্ৰহণ কৰিছে।'
    expect(chrf(google, pib)).toBeCloseTo(92.2216, 3)
    expect(chrf(sarvam, pib)).toBeCloseTo(71.9184, 3)
  })

  test('the edges: identical, a short prefix, nothing shared, nothing at all', () => {
    expect(chrf('The cat sat.', 'The cat sat.')).toBeCloseTo(100, 3)
    expect(chrf('ab', 'abcdefgh')).toBeCloseTo(23.4043, 3)
    expect(chrf('x', 'y')).toBe(0)
    expect(chrf('', 'abc')).toBe(0)
  })
})

describe('a copy', () => {
  test('is a reference within chrF 90 of what Google writes for the same English', () => {
    const pib = 'বিমানৰ ৰক্ষণাবেক্ষণ, মেৰামতি আৰু অভাৰহ’ল খণ্ডত ভাৰতে এই বৃহৎ পদক্ষেপ গ্ৰহণ কৰিছে।'
    expect(isCopy('বিমান ৰক্ষণাবেক্ষণ, মেৰামতি, আৰু অভাৰহ’ল খণ্ডত ভাৰতে এই বৃহৎ পদক্ষেপ গ্ৰহণ কৰিছে।', pib)).toBe(true)
    expect(isCopy('ভাৰতে বিমান ৰক্ষণাবেক্ষণ, মেৰামতি আৰু অভাৰহল (MRO) খণ্ডত এই গুৰুত্বপূৰ্ণ পদক্ষেপ গ্ৰহণ কৰিছে।', pib)).toBe(false)
  })
})
