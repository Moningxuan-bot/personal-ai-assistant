class Meme {
  final String id;
  final String title;
  final String source;
  final String? url;
  final String? summary;
  final String? tags;
  final bool kept;
  final bool discarded;
  final bool asked;
  final DateTime fetchedAt;

  const Meme({
    required this.id,
    required this.title,
    this.source = 'bilibili',
    this.url,
    this.summary,
    this.tags,
    this.kept = false,
    this.discarded = false,
    this.asked = false,
    required this.fetchedAt,
  });

  factory Meme.fromJson(Map<String, dynamic> json) {
    return Meme(
      id: json['id'] as String,
      title: json['title'] as String,
      source: (json['source'] as String?) ?? 'bilibili',
      url: json['url'] as String?,
      summary: json['summary'] as String?,
      tags: json['tags'] as String?,
      kept: (json['kept'] as bool?) ?? false,
      discarded: (json['discarded'] as bool?) ?? false,
      asked: (json['asked'] as bool?) ?? false,
      fetchedAt: DateTime.parse(json['fetched_at'] as String),
    );
  }
}
