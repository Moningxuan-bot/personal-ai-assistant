import 'package:flutter_test/flutter_test.dart';
import 'package:ai_assistant/models/meme.dart';

void main() {
  group('Meme', () {
    final sampleJson = {
      'id': '880e8400-e29b-41d4-a716-446655440003',
      'title': '卧槽，这也太离谱了吧',
      'source': 'bilibili',
      'url': 'https://bilibili.com/video/BV1xx41127xx',
      'summary': '一个剪辑师把鬼畜做到了一帧一帧对嘴型，播放量三天破千万',
      'tags': '鬼畜,搞笑,神剪辑',
      'kept': false,
      'discarded': false,
      'asked': false,
      'fetched_at': '2026-06-16T22:00:00Z',
    };

    test('fromJson parses all fields', () {
      final meme = Meme.fromJson(sampleJson);
      expect(meme.id, '880e8400-e29b-41d4-a716-446655440003');
      expect(meme.title, '卧槽，这也太离谱了吧');
      expect(meme.source, 'bilibili');
      expect(meme.kept, false);
      expect(meme.discarded, false);
      expect(meme.summary, isNotNull);
    });

    test('fromJson handles missing optional fields', () {
      final minimal = {
        'id': '990e8400-e29b-41d4-a716-446655440004',
        'title': '测试梗',
        'source': 'bilibili',
        'kept': false,
        'discarded': false,
        'asked': false,
        'fetched_at': '2026-06-16T22:00:00Z',
      };
      final meme = Meme.fromJson(minimal);
      expect(meme.url, isNull);
      expect(meme.summary, isNull);
      expect(meme.tags, isNull);
    });
  });
}
