"""Dated upload edition. Preserve the original video and earlier PDF editions."""
from pathlib import Path
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import build_submission_054 as source

VIDEO = ROOT.parent / 'AI大赛演示视频.mp4'
FINAL = ROOT / '参赛材料/0.5.4-提交版-20261103'
OUT = ROOT / 'output/pdf/final-20261103'

REPLACEMENTS = {
    '演示视频按通知另交5至8分钟MP4，本材料包含讲稿，不代表视频已经录制。':
        '参赛者已于2026年11月3日提供实际操作演示MP4，按原文件随附交付；本材料中的讲稿作为说明附件保留。',
    '实际试用应用，报告分析页白屏问题，反馈修复后恢复；提出完整性、评测和提交准备要求。':
        '实际试用应用，报告分析页白屏问题，反馈修复后恢复；提出完整性、评测和提交准备要求；自行录制并提供作品演示视频。',
    '也不能将未完成的独立评价或视频录制写为既有贡献。':
        '独立人工评价未完成，不计入已完成贡献。',
    '5至8分钟真实视频由参赛者录制，提供实际运行过程，不以脚本或离线回放冒充实时模型响应。':
        '参赛者已提供实际操作演示视频。交付整理核对了视频元信息并抽查画面；不把抽样画面检查描述为完整逐句音画审核。',
    '录制检查': '视频交付与检查',
    '录制5至8分钟MP4，隐藏密钥和无关窗口；实际操作并讲解。模型失败就如实说明，不把预写答案当实时输出。结束后检查声音、画面、时长与播放。讲稿并非已完成视频。':
        '演示视频已由参赛者录制并提供：1920×1080，约8分29.8秒，30,685,975字节。交付整理保留原始MP4，不裁剪、不加速、不改写内容。提交前由本人完整播放核对声音、画面及凭据遮蔽，最终接收以平台审核为准。',
}


def main():
    assert VIDEO.is_file()
    info = json.loads((ROOT / 'output/video-review-20261103/metadata.json').read_text(encoding='utf-8'))
    assert hashlib.sha256(VIDEO.read_bytes()).hexdigest() == info['sha256']
    source.DATE = '2026-11-03'
    source.FINAL = FINAL
    source.OUT = OUT
    original_p = source.layout.p

    def current_p(text, style='BodyX'):
        value = str(text)
        for before, after in REPLACEMENTS.items():
            value = value.replace(before, after)
        return original_p(value, style)

    source.layout.p = current_p
    try:
        source.main()
    finally:
        source.layout.p = original_p
    manifest = json.loads((FINAL / 'materials-manifest.json').read_text(encoding='utf-8'))
    manifest.update(status='PDF及原始视频已备齐；本人最终核对、平台提交待完成',
                    video={k: info[k] for k in ['bytes', 'duration_seconds', 'width', 'height', 'sha256']},
                    video_modified=False, video_review='metadata_and_sampled_frames_only',
                    duration_within_notice_range=info['duration_5_to_8_minutes'],
                    entrant_instruction='参赛者明确要求保留原视频继续推进；不据此声明赛事已豁免时长要求',
                    submitted_to_platform=False)
    raw = json.dumps(manifest, ensure_ascii=False, indent=2)
    for directory in [FINAL, OUT]:
        (directory / 'materials-manifest.json').write_text(raw, encoding='utf-8')
    checklist = (FINAL / '上传清单.md').read_text(encoding='utf-8')
    checklist = checklist.replace('参赛者另录5至8分钟MP4；尚未提供', '原视频已提供；按原文件上传，视频内容未修改')
    checklist = checklist.replace('- [ ] 录制并播放检查5至8分钟MP4，注意不展示密钥。',
        '- [x] 已收到参赛者录制的MP4，保留原文件。\n- [ ] 本人完整播放核对声音、画面及凭据遮蔽，检查平台实际接收要求。')
    checklist = checklist.replace('贸势有据-0.5.4-源码与运行包.zip', '贸势有据-0.5.4-源码与运行包-20261103.zip')
    (FINAL / '上传清单.md').write_text(checklist, encoding='utf-8')
    print(json.dumps({'final_directory': str(FINAL), 'video_original_sha256': info['sha256'],
                      'video_modified': False, 'submitted': False}, ensure_ascii=False))


if __name__ == '__main__':
    main()
