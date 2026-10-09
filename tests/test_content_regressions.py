"""Regression coverage for review issues #2 and #3; no network required."""

import importlib.util
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('check_content', ROOT / 'scripts/check_content.py')
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)

# Ordered markers from the pre-migration text at commit 3a0a2f97eb1c742fa1e5b79d65107f5d3b18a6c5.
# Keeping this independent of current Markdown catches missing or duplicated
# timestamps as well as syntax damage, without fetching old files during tests.
ORIGINAL_TIMESTAMPS = {
    7: ['[00:05:00]', '[00:10:00]', '[00:15:00]'],
    8: ['[00:10:00]', '[00:25:00]'],
    10: ['[00:05:00]', '[00:10:00]', '[00:15:00]', '[00:21:00]', '[00:25:00]', '[00:30:00]'],
}


class ContentRegressions(unittest.TestCase):
    def test_all_original_timestamps_survive_in_order(self):
        for episode in range(1, 14):
            with self.subTest(episode=episode):
                text = (ROOT / f'Episode-{episode}.md').read_text(encoding='utf-8')
                self.assertEqual(re.findall(r'\[\d{2}:\d{2}:\d{2}\]', text), ORIGINAL_TIMESTAMPS.get(episode, []))
                self.assertEqual(checker.episode_format_errors(text), [])

    def test_seven_split_markers_are_rejected(self):
        broken_lines = [
            '**本当に美味しいですよ。[00:** 05:00] 続き',
            '**他のプレイヤーよりも遥かに優れた力を持つようになりました。[00:** 10:00]続き',
            '**騒ぎが起こっている間に、GMが現れました。[00:** 10:00] 続き',
            '**[00:** 05:00] 続き',
            '**知っていることを考慮して、[00:** 15:00] 続き',
            '**その瞬間、[00:** 21:00] 続き',
            '**彼らがたどり着いた最終的な解決策は、[00:** 30:00] 続き',
        ]
        for line in broken_lines:
            with self.subTest(line=line):
                errors = checker.episode_format_errors(line)
                self.assertTrue(any('malformed timestamp' in error for error in errors))
                self.assertTrue(any('non-speaker' in error for error in errors))

    def test_prose_colons_are_not_speakers(self):
        for label in ['解決策：', 'ですが、VTechは以下のウェブサイトを閉鎖しました：', 'https:', 'その瞬間、[00:']:
            with self.subTest(label=label):
                self.assertFalse(checker.is_speaker_label(label))
                self.assertTrue(checker.episode_format_errors(f'**{label}** 続き'))

    def test_real_speakers_and_intact_time_are_valid(self):
        for label in ['ジャック:', 'NSA:', '被害者1:', 'ジャック（JACK）イントロ:', 'JACK [アウトロ]:', 'ジャック (OUTRO):']:
            with self.subTest(label=label):
                self.assertTrue(checker.is_speaker_label(label))
                self.assertEqual(checker.episode_format_errors(f'**{label}** その瞬間、[00:21:00] 続き'), [])

    def test_plain_prose_colon_and_url_are_valid(self):
        text = '解決策：続きを確認する。\nその瞬間、[00:21:00] 続き\nhttps://example.com:443/'
        self.assertEqual(checker.episode_format_errors(text), [])

    def test_removed_false_speaker_emphasis_does_not_return(self):
        for episode in (2, 3, 5, 7, 8, 10, 13):
            text = (ROOT / f'Episode-{episode}.md').read_text(encoding='utf-8')
            with self.subTest(episode=episode):
                self.assertEqual(checker.episode_format_errors(text), [])

    def test_lateral_movement_destination_is_administrator_machine(self):
        text = (ROOT / 'Episode-10.md').read_text(encoding='utf-8')
        self.assertIn('管理者のマシンへ横展開できるでしょう。', text)
        self.assertIn('彼のマシンへ横展開してそこにインプラントを配置しました。', text)
        self.assertNotIn('マシンに別の端末へ横展開', text)


if __name__ == '__main__':
    unittest.main()
