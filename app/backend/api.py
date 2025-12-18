"""
Flask APIエンドポイント
"""
from flask import Flask, request, jsonify, send_file, Response, send_from_directory
from flask_cors import CORS
from pathlib import Path
import sys
import json
import logging
import queue
import threading
from datetime import datetime
from typing import Optional

# パス設定（直接実行時のため）
APP_DIR = Path(__file__).parent.parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from backend.aggregator import SalesAggregator, AccountsCalculator, ExcelExporter, SchoolMasterMismatchError, CumulativeAggregator
from backend.services import FileHandler, DatabaseService

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# フロントエンドディレクトリ
FRONTEND_DIR = Path(__file__).parent.parent / 'frontend'


def create_app(config=None):
    """
    Flaskアプリケーションファクトリ

    Args:
        config: 設定オブジェクト

    Returns:
        Flask: アプリケーションインスタンス
    """
    # 静的ファイル配信設定
    app = Flask(
        __name__,
        static_folder=str(FRONTEND_DIR / 'dist' / 'assets') if (FRONTEND_DIR / 'dist').exists() else None,
        static_url_path='/assets'
    )

    # CORS設定（フロントエンドからのアクセス許可）
    CORS(app, origins=["http://localhost:*", "http://127.0.0.1:*"])

    # 設定読み込み
    if config:
        app.config.from_object(config)
    else:
        from config import get_config
        app.config.from_object(get_config())

    # ディレクトリ設定
    app.config.setdefault('UPLOAD_DIR', Path(__file__).parent.parent / 'uploads')
    app.config.setdefault('OUTPUT_DIR', Path.home() / 'Downloads')
    app.config.setdefault('MAX_CONTENT_LENGTH', 16 * 1024 * 1024)

    # ディレクトリ作成
    Path(app.config['UPLOAD_DIR']).mkdir(parents=True, exist_ok=True)

    # 進捗通知用キュー
    progress_queues = {}

    # サービス初期化
    file_handler = FileHandler(Path(app.config['UPLOAD_DIR']))

    # 一時データ保存用
    app.session_data = {}

    @app.route('/api/health', methods=['GET'])
    def health_check():
        """ヘルスチェック"""
        return jsonify({'status': 'ok', 'timestamp': datetime.now().isoformat()})

    @app.route('/api/upload', methods=['POST'])
    def upload_files():
        """ファイルアップロード"""
        try:
            files = request.files

            # 必須ファイルチェック
            required = ['sales_file', 'accounts_file', 'master_file']
            missing = [f for f in required if f not in files]
            if missing:
                return jsonify({
                    'status': 'error',
                    'message': f'必須ファイルがありません: {missing}'
                }), 400

            # ファイル保存
            saved_files = {}
            for key in required:
                file = files[key]
                if file.filename:
                    filepath = file_handler.save_uploaded_file(
                        file, f"{key}_{file.filename}"
                    )
                    saved_files[key] = str(filepath)

            # セッションに保存
            session_id = datetime.now().strftime('%Y%m%d%H%M%S')
            app.session_data[session_id] = saved_files

            return jsonify({
                'status': 'success',
                'session_id': session_id,
                'files': {k: Path(v).name for k, v in saved_files.items()}
            })

        except Exception as e:
            logger.error(f"アップロードエラー: {e}")
            return jsonify({'status': 'error', 'message': str(e)}), 500

    @app.route('/api/aggregate', methods=['POST'])
    def aggregate():
        """集計実行"""
        try:
            data = request.get_json()
            session_id = data.get('session_id')
            fiscal_year = data.get('fiscal_year')
            month = data.get('month')

            # セッションデータ取得
            if session_id not in app.session_data:
                return jsonify({
                    'status': 'error',
                    'message': 'セッションが見つかりません。ファイルを再アップロードしてください。'
                }), 400

            files = app.session_data[session_id]

            # ファイル読み込み
            sales_df = file_handler.read_sales_csv(Path(files['sales_file']))
            accounts_df = file_handler.read_accounts_csv(Path(files['accounts_file']))
            master_df = file_handler.read_master_excel(Path(files['master_file']))

            # 集計実行
            aggregator = SalesAggregator(sales_df, master_df)
            result = aggregator.aggregate_all()

            # 会員率計算
            accounts_calc = AccountsCalculator(accounts_df)
            accounts_result_df = accounts_calc.calculate()

            # Excel出力
            output_dir = Path(app.config['OUTPUT_DIR'])
            filename = f"SP_SalesResult_{fiscal_year}{month:02d}.xlsx" if fiscal_year and month else None
            exporter = ExcelExporter(
                result,
                output_dir=output_dir,
                filename=filename,
                accounts_df=accounts_result_df
            )
            output_path = exporter.export()

            # 結果をセッションに保存
            app.session_data[session_id]['output_path'] = str(output_path)
            app.session_data[session_id]['result'] = result

            return jsonify({
                'status': 'success',
                'summary': result.summary.to_dict(),
                'output_file': output_path.name,
                'statistics': {
                    'branch_count': len(result.branch_sales),
                    'salesman_count': len(result.salesman_sales),
                    'school_count': len(result.school_sales),
                    'event_count': len(result.event_sales),
                    'unmatched_count': len(result.unmatched_schools)
                }
            })

        except SchoolMasterMismatchError as e:
            logger.error(f"マスタ不一致エラー: {e}")
            return jsonify({
                'status': 'error',
                'error_type': 'master_mismatch',
                'message': str(e),
                'unmatched_schools': e.unmatched_schools
            }), 400
        except ValueError as e:
            logger.error(f"バリデーションエラー: {e}")
            return jsonify({'status': 'error', 'message': str(e)}), 400
        except Exception as e:
            logger.error(f"集計エラー: {e}")
            return jsonify({'status': 'error', 'message': str(e)}), 500

    @app.route('/api/download/<session_id>', methods=['GET'])
    def download_file(session_id):
        """Excelファイルダウンロード"""
        try:
            if session_id not in app.session_data:
                return jsonify({
                    'status': 'error',
                    'message': 'セッションが見つかりません'
                }), 404

            output_path = app.session_data[session_id].get('output_path')
            if not output_path or not Path(output_path).exists():
                return jsonify({
                    'status': 'error',
                    'message': 'ファイルが見つかりません'
                }), 404

            return send_file(
                output_path,
                as_attachment=True,
                download_name=Path(output_path).name
            )

        except Exception as e:
            logger.error(f"ダウンロードエラー: {e}")
            return jsonify({'status': 'error', 'message': str(e)}), 500

    @app.route('/api/save-db', methods=['POST'])
    def save_to_database():
        """データベースに保存"""
        try:
            data = request.get_json()
            session_id = data.get('session_id')

            if session_id not in app.session_data:
                return jsonify({
                    'status': 'error',
                    'message': 'セッションが見つかりません'
                }), 404

            output_path = app.session_data[session_id].get('output_path')
            if not output_path:
                return jsonify({
                    'status': 'error',
                    'message': '先に集計を実行してください'
                }), 400

            db_service = DatabaseService()
            success = db_service.save_to_database(Path(output_path))

            if success:
                return jsonify({'status': 'success', 'message': 'データベースに保存しました'})
            else:
                return jsonify({
                    'status': 'error',
                    'message': 'データベース保存に失敗しました'
                }), 500

        except Exception as e:
            logger.error(f"DB保存エラー: {e}")
            return jsonify({'status': 'error', 'message': str(e)}), 500

    @app.route('/api/publish', methods=['POST'])
    def publish_dashboard():
        """ダッシュボード生成・公開"""
        try:
            db_service = DatabaseService()

            # ダッシュボード生成
            dashboard_path = db_service.generate_dashboard()
            if not dashboard_path:
                return jsonify({
                    'status': 'error',
                    'message': 'ダッシュボード生成に失敗しました'
                }), 500

            # 公開
            from config import Config
            success = db_service.publish_dashboard(Config.PUBLISH_PATH)

            return jsonify({
                'status': 'success',
                'message': 'ダッシュボードを公開しました',
                'dashboard_path': str(dashboard_path)
            })

        except Exception as e:
            logger.error(f"公開エラー: {e}")
            return jsonify({'status': 'error', 'message': str(e)}), 500

    @app.route('/api/config', methods=['GET'])
    def get_app_config():
        """設定情報取得"""
        return jsonify({
            'fiscal_years': list(range(2020, datetime.now().year + 2)),
            'months': list(range(1, 13)),
            'current_year': datetime.now().year,
            'current_month': datetime.now().month
        })

    @app.route('/api/progress/<session_id>', methods=['GET'])
    def get_progress(session_id):
        """進捗状況取得（Server-Sent Events）"""
        def generate():
            q = progress_queues.get(session_id, queue.Queue())
            while True:
                try:
                    message = q.get(timeout=30)
                    yield f"data: {json.dumps(message)}\n\n"
                    if message.get('percentage', 0) >= 100:
                        break
                except queue.Empty:
                    yield f"data: {json.dumps({'status': 'waiting'})}\n\n"

        return Response(generate(), mimetype='text/event-stream')

    # ========== 累積集計API ==========

    @app.route('/api/cumulative/upload', methods=['POST'])
    def cumulative_upload():
        """累積集計用ファイルアップロード"""
        try:
            files = request.files

            if 'input_file' not in files:
                return jsonify({
                    'status': 'error',
                    'message': '入力ファイルがありません'
                }), 400

            file = files['input_file']
            if not file.filename:
                return jsonify({
                    'status': 'error',
                    'message': 'ファイルが選択されていません'
                }), 400

            # ファイル保存
            filepath = file_handler.save_uploaded_file(
                file, f"cumulative_{file.filename}"
            )

            # セッションに保存
            session_id = f"cum_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            app.session_data[session_id] = {
                'input_file': str(filepath)
            }

            # 既存累積ファイルがある場合
            existing_file = files.get('existing_file')
            if existing_file and existing_file.filename:
                existing_filepath = file_handler.save_uploaded_file(
                    existing_file, f"existing_{existing_file.filename}"
                )
                app.session_data[session_id]['existing_file'] = str(existing_filepath)

            return jsonify({
                'status': 'success',
                'session_id': session_id,
                'filename': file.filename,
                'existing_filename': existing_file.filename if existing_file and existing_file.filename else None
            })

        except Exception as e:
            logger.error(f"累積集計アップロードエラー: {e}")
            return jsonify({'status': 'error', 'message': str(e)}), 500

    @app.route('/api/cumulative/aggregate', methods=['POST'])
    def cumulative_aggregate():
        """累積集計実行"""
        try:
            data = request.get_json()
            session_id = data.get('session_id')
            year = data.get('year')
            month = data.get('month')
            fiscal_year = data.get('fiscal_year')

            # セッションデータ取得
            if session_id not in app.session_data:
                return jsonify({
                    'status': 'error',
                    'message': 'セッションが見つかりません。ファイルを再アップロードしてください。'
                }), 400

            session = app.session_data[session_id]
            input_path = Path(session['input_file'])

            # 既存ファイルパス（アップロードされていれば）
            existing_file_path = session.get('existing_file')
            if existing_file_path:
                existing_file_path = Path(existing_file_path)
                # 既存ファイルの親ディレクトリを出力先とする
                output_dir = existing_file_path.parent
            else:
                output_dir = Path(app.config['OUTPUT_DIR'])

            # 累積集計実行
            aggregator = CumulativeAggregator(
                input_path=input_path,
                output_dir=output_dir,
                year=year,
                month=month,
                fiscal_year=fiscal_year,
                existing_file_path=existing_file_path
            )
            result = aggregator.process()

            # 結果をセッションに保存
            app.session_data[session_id]['output_path'] = result['outputPath']
            app.session_data[session_id]['result'] = result

            return jsonify({
                'status': 'success',
                'schoolCount': result['schoolCount'],
                'eventCount': result['eventCount'],
                'outputFilename': result['outputFilename']
            })

        except ValueError as e:
            logger.error(f"累積集計バリデーションエラー: {e}")
            return jsonify({'status': 'error', 'message': str(e)}), 400
        except Exception as e:
            logger.error(f"累積集計エラー: {e}")
            return jsonify({'status': 'error', 'message': str(e)}), 500

    @app.route('/api/cumulative/download/<session_id>', methods=['GET'])
    def cumulative_download(session_id):
        """累積集計結果ダウンロード"""
        try:
            if session_id not in app.session_data:
                return jsonify({
                    'status': 'error',
                    'message': 'セッションが見つかりません'
                }), 404

            output_path = app.session_data[session_id].get('output_path')
            if not output_path or not Path(output_path).exists():
                return jsonify({
                    'status': 'error',
                    'message': 'ファイルが見つかりません'
                }), 404

            return send_file(
                output_path,
                as_attachment=True,
                download_name=Path(output_path).name
            )

        except Exception as e:
            logger.error(f"累積集計ダウンロードエラー: {e}")
            return jsonify({'status': 'error', 'message': str(e)}), 500

    # ========== 複数ファイル累積集計API ==========

    @app.route('/api/cumulative/upload-multiple', methods=['POST'])
    def cumulative_upload_multiple():
        """複数ファイル累積集計用アップロード"""
        try:
            files = request.files
            form_data = request.form

            # ファイル情報を取得
            files_info_str = form_data.get('files_info')
            if not files_info_str:
                return jsonify({
                    'status': 'error',
                    'message': 'ファイル情報がありません'
                }), 400

            files_info = json.loads(files_info_str)
            fiscal_year = int(form_data.get('fiscal_year', 0))

            # 各ファイルを保存
            saved_files = []
            for info in files_info:
                file_key = f"input_file_{info['index']}"
                if file_key not in files:
                    return jsonify({
                        'status': 'error',
                        'message': f'ファイル {file_key} が見つかりません'
                    }), 400

                file = files[file_key]
                if not file.filename:
                    continue

                filepath = file_handler.save_uploaded_file(
                    file, f"cumulative_{info['year']}_{info['month']}_{file.filename}"
                )
                saved_files.append({
                    'path': str(filepath),
                    'year': info['year'],
                    'month': info['month'],
                    'filename': file.filename
                })

            if not saved_files:
                return jsonify({
                    'status': 'error',
                    'message': '有効なファイルがありません'
                }), 400

            # セッションに保存
            session_id = f"cum_multi_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            app.session_data[session_id] = {
                'input_files': saved_files,
                'fiscal_year': fiscal_year
            }

            # 既存累積ファイルのパスがある場合（テキスト入力からの直接パス）
            existing_file_path = form_data.get('existing_file_path')
            if existing_file_path:
                existing_path = Path(existing_file_path)
                if existing_path.exists():
                    app.session_data[session_id]['existing_file'] = str(existing_path)
                    logger.info(f"既存ファイルパス指定: {existing_path}")
                else:
                    logger.warning(f"指定された既存ファイルが存在しません: {existing_file_path}")

            return jsonify({
                'status': 'success',
                'session_id': session_id,
                'file_count': len(saved_files)
            })

        except Exception as e:
            logger.error(f"複数ファイルアップロードエラー: {e}")
            return jsonify({'status': 'error', 'message': str(e)}), 500

    @app.route('/api/cumulative/aggregate-multiple', methods=['POST'])
    def cumulative_aggregate_multiple():
        """複数ファイル累積集計実行"""
        try:
            data = request.get_json()
            session_id = data.get('session_id')

            # セッションデータ取得
            if session_id not in app.session_data:
                return jsonify({
                    'status': 'error',
                    'message': 'セッションが見つかりません。ファイルを再アップロードしてください。'
                }), 400

            session = app.session_data[session_id]
            input_files = session['input_files']
            fiscal_year = session['fiscal_year']

            # 既存ファイルパス（アップロードされていれば）
            existing_file_path = session.get('existing_file')
            if existing_file_path:
                existing_file_path = Path(existing_file_path)
                output_dir = existing_file_path.parent
            else:
                output_dir = Path(app.config['OUTPUT_DIR'])

            # 年月順にソート（古い順）
            input_files_sorted = sorted(input_files, key=lambda x: (x['year'], x['month']))

            # 処理結果
            total_school_count = 0
            total_event_count = 0
            processed_months = []
            output_path = None

            # 各ファイルを順番に処理
            for i, file_info in enumerate(input_files_sorted):
                input_path = Path(file_info['path'])
                year = file_info['year']
                month = file_info['month']

                logger.info(f"処理中 ({i+1}/{len(input_files_sorted)}): {year}年{month}月")

                # 最初のファイル以降は、出力ファイルを既存ファイルとして使用
                if i > 0 and output_path:
                    existing_file_path = Path(output_path)

                aggregator = CumulativeAggregator(
                    input_path=input_path,
                    output_dir=output_dir,
                    year=year,
                    month=month,
                    fiscal_year=fiscal_year,
                    existing_file_path=existing_file_path
                )
                result = aggregator.process()

                output_path = result['outputPath']
                total_school_count = result['schoolCount']
                total_event_count = result['eventCount']
                processed_months.append(f"{year}年{month}月")

            # 結果をセッションに保存
            app.session_data[session_id]['output_path'] = output_path
            app.session_data[session_id]['result'] = {
                'schoolCount': total_school_count,
                'eventCount': total_event_count,
                'processedCount': len(input_files_sorted),
                'processedMonths': ', '.join(processed_months)
            }

            return jsonify({
                'status': 'success',
                'schoolCount': total_school_count,
                'eventCount': total_event_count,
                'processedCount': len(input_files_sorted),
                'processedMonths': ', '.join(processed_months),
                'fiscalYear': fiscal_year,
                'outputFilename': Path(output_path).name if output_path else None,
                'outputPath': str(output_path) if output_path else None
            })

        except ValueError as e:
            logger.error(f"複数ファイル累積集計バリデーションエラー: {e}")
            return jsonify({'status': 'error', 'message': str(e)}), 400
        except Exception as e:
            logger.error(f"複数ファイル累積集計エラー: {e}")
            return jsonify({'status': 'error', 'message': str(e)}), 500

    # ========== 実績反映API ==========

    @app.route('/api/publish/check-duplicates', methods=['POST'])
    def check_duplicates():
        """重複データチェック"""
        try:
            data = request.get_json()
            filenames = data.get('filenames', [])

            # ファイル名から年月を抽出して重複チェック
            duplicates = []
            db_service = DatabaseService()

            for filename in filenames:
                # ファイル名から年月を抽出（SP_SalesResult_202504.xlsx → 2025年4月）
                import re
                match = re.search(r'(\d{4})(\d{2})\.xlsx', filename)
                if match:
                    year = int(match.group(1))
                    month = int(match.group(2))

                    # DBで既存データをチェック
                    if db_service.check_month_exists(year, month):
                        duplicates.append(f"{year}年{month}月")

            return jsonify({
                'status': 'success',
                'duplicates': duplicates
            })

        except Exception as e:
            logger.error(f"重複チェックエラー: {e}")
            return jsonify({'status': 'error', 'message': str(e)}), 500

    @app.route('/api/publish/upload', methods=['POST'])
    def publish_upload():
        """実績反映用ファイルアップロード"""
        try:
            files = request.files
            form_data = request.form
            file_count = int(form_data.get('file_count', 0))

            saved_files = []
            for i in range(file_count):
                file_key = f"file_{i}"
                if file_key in files:
                    file = files[file_key]
                    if file.filename:
                        filepath = file_handler.save_uploaded_file(
                            file, f"publish_{file.filename}"
                        )
                        saved_files.append({
                            'path': str(filepath),
                            'filename': file.filename
                        })

            if not saved_files:
                return jsonify({
                    'status': 'error',
                    'message': '有効なファイルがありません'
                }), 400

            # セッションに保存
            session_id = f"pub_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            app.session_data[session_id] = {
                'files': saved_files
            }

            return jsonify({
                'status': 'success',
                'session_id': session_id,
                'file_count': len(saved_files)
            })

        except Exception as e:
            logger.error(f"実績反映アップロードエラー: {e}")
            return jsonify({'status': 'error', 'message': str(e)}), 500

    @app.route('/api/publish/import', methods=['POST'])
    def publish_import():
        """実績反映（DBインポート）実行"""
        try:
            data = request.get_json()
            session_id = data.get('session_id')

            if session_id not in app.session_data:
                return jsonify({
                    'status': 'error',
                    'message': 'セッションが見つかりません'
                }), 400

            session = app.session_data[session_id]
            files = session['files']

            # 各ファイルをインポート
            imported_count = 0
            for file_info in files:
                filepath = Path(file_info['path'])
                if filepath.exists():
                    try:
                        # 既存のimporterを使用
                        from importer import import_excel
                        import_excel(str(filepath))
                        imported_count += 1
                        logger.info(f"インポート完了: {file_info['filename']}")
                    except Exception as e:
                        logger.error(f"インポートエラー ({file_info['filename']}): {e}")

            return jsonify({
                'status': 'success',
                'fileCount': imported_count
            })

        except Exception as e:
            logger.error(f"実績反映エラー: {e}")
            return jsonify({'status': 'error', 'message': str(e)}), 500

    @app.route('/api/publish/generate-dashboard', methods=['POST'])
    def generate_dashboard():
        """ダッシュボード生成"""
        try:
            db_service = DatabaseService()
            dashboard_path = db_service.generate_dashboard()

            if dashboard_path:
                # 生成日時を記録
                app.config['DASHBOARD_LAST_GENERATED'] = datetime.now().isoformat()
                return jsonify({
                    'status': 'success',
                    'path': str(dashboard_path)
                })
            else:
                return jsonify({
                    'status': 'error',
                    'message': 'ダッシュボード生成に失敗しました'
                }), 500

        except Exception as e:
            logger.error(f"ダッシュボード生成エラー: {e}")
            return jsonify({'status': 'error', 'message': str(e)}), 500

    @app.route('/api/publish/dashboard-status', methods=['GET'])
    def dashboard_status():
        """ダッシュボード状態取得"""
        try:
            last_generated = app.config.get('DASHBOARD_LAST_GENERATED')
            last_published = app.config.get('DASHBOARD_LAST_PUBLISHED')

            # ダッシュボードHTMLファイルの存在確認
            dashboard_path = APP_DIR.parent / 'dashboard.html'
            has_dashboard = dashboard_path.exists()

            return jsonify({
                'status': 'success',
                'dashboard': {
                    'lastGenerated': last_generated,
                    'lastPublished': last_published,
                    'hasUnpublishedChanges': last_generated and (not last_published or last_generated > last_published)
                }
            })

        except Exception as e:
            logger.error(f"ダッシュボード状態取得エラー: {e}")
            return jsonify({'status': 'error', 'message': str(e)}), 500

    @app.route('/api/publish/preview', methods=['GET'])
    def preview_dashboard():
        """ダッシュボードプレビュー"""
        try:
            # 最新のダッシュボードファイルを検索
            dashboard_dir = APP_DIR.parent
            dashboard_files = list(dashboard_dir.glob('dashboard_*.html'))

            if dashboard_files:
                # 最新のファイルを取得（更新日時順）
                latest_dashboard = max(dashboard_files, key=lambda p: p.stat().st_mtime)
                return send_file(str(latest_dashboard), mimetype='text/html')
            else:
                return jsonify({
                    'status': 'error',
                    'message': 'ダッシュボードが生成されていません'
                }), 404

        except Exception as e:
            logger.error(f"プレビューエラー: {e}")
            return jsonify({'status': 'error', 'message': str(e)}), 500

    @app.route('/api/publish/publish-dashboard', methods=['POST'])
    def publish_dashboard_api():
        """ダッシュボード公開"""
        try:
            db_service = DatabaseService()
            from config import Config
            success = db_service.publish_dashboard(Config.PUBLISH_PATH)

            if success:
                app.config['DASHBOARD_LAST_PUBLISHED'] = datetime.now().isoformat()
                # 公開先URLを構築
                publish_url = str(Config.PUBLISH_PATH / "dashboard.html")
                return jsonify({
                    'status': 'success',
                    'message': 'ダッシュボードを公開しました',
                    'publishUrl': publish_url
                })
            else:
                return jsonify({
                    'status': 'error',
                    'message': 'ダッシュボード公開に失敗しました'
                }), 500

        except Exception as e:
            logger.error(f"ダッシュボード公開エラー: {e}")
            return jsonify({'status': 'error', 'message': str(e)}), 500

    @app.route('/api/publish/github-pages', methods=['POST'])
    def publish_to_github_pages():
        """GitHub Pagesにダッシュボードを公開"""
        import subprocess
        import shutil

        try:
            from config import Config

            # 最新のダッシュボードファイルを検索
            dashboard_dir = APP_DIR.parent
            dashboard_files = list(dashboard_dir.glob('dashboard_*.html'))

            if not dashboard_files:
                return jsonify({
                    'status': 'error',
                    'message': 'ダッシュボードが生成されていません。先に実績反映を行ってください。'
                }), 400

            # 最新のファイルを取得
            latest_dashboard = max(dashboard_files, key=lambda p: p.stat().st_mtime)
            logger.info(f"最新ダッシュボード: {latest_dashboard}")

            # GitHub Pagesリポジトリのパス
            repo_path = Config.GITHUB_PAGES_REPO_PATH

            # リポジトリフォルダが存在するか確認
            if not repo_path.exists():
                return jsonify({
                    'status': 'error',
                    'message': f'GitHub Pagesリポジトリフォルダが見つかりません: {repo_path}'
                }), 400

            # index.htmlとしてコピー
            index_path = repo_path / 'index.html'
            shutil.copy2(latest_dashboard, index_path)
            logger.info(f"ダッシュボードをコピー: {latest_dashboard} -> {index_path}")

            # Gitコマンドを実行
            try:
                # git add
                subprocess.run(
                    ['git', 'add', 'index.html'],
                    cwd=str(repo_path),
                    check=True,
                    capture_output=True,
                    text=True
                )

                # git commit
                commit_result = subprocess.run(
                    ['git', 'commit', '-m', f'Update dashboard {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'],
                    cwd=str(repo_path),
                    capture_output=True,
                    text=True
                )

                # 変更がない場合はスキップ
                if commit_result.returncode != 0 and 'nothing to commit' in commit_result.stdout:
                    logger.info("変更なし、コミットをスキップ")
                elif commit_result.returncode != 0:
                    raise subprocess.CalledProcessError(commit_result.returncode, 'git commit', commit_result.stderr)

                # git push
                push_result = subprocess.run(
                    ['git', 'push'],
                    cwd=str(repo_path),
                    check=True,
                    capture_output=True,
                    text=True
                )
                logger.info(f"git push完了: {push_result.stdout}")

            except subprocess.CalledProcessError as e:
                logger.error(f"Gitコマンドエラー: {e.stderr}")
                return jsonify({
                    'status': 'error',
                    'message': f'Git操作に失敗しました: {e.stderr}'
                }), 500

            # 公開完了
            app.config['GITHUB_PAGES_LAST_PUBLISHED'] = datetime.now().isoformat()

            return jsonify({
                'status': 'success',
                'message': 'GitHub Pagesに公開しました',
                'publishUrl': Config.GITHUB_PAGES_URL
            })

        except Exception as e:
            logger.error(f"GitHub Pages公開エラー: {e}")
            return jsonify({'status': 'error', 'message': str(e)}), 500

    @app.route('/api/publish/github-pages-status', methods=['GET'])
    def github_pages_status():
        """GitHub Pages公開状態を取得"""
        try:
            from config import Config

            repo_path = Config.GITHUB_PAGES_REPO_PATH
            repo_exists = repo_path.exists()
            index_exists = (repo_path / 'index.html').exists() if repo_exists else False

            return jsonify({
                'status': 'success',
                'githubPages': {
                    'repoExists': repo_exists,
                    'indexExists': index_exists,
                    'lastPublished': app.config.get('GITHUB_PAGES_LAST_PUBLISHED'),
                    'publishUrl': Config.GITHUB_PAGES_URL
                }
            })

        except Exception as e:
            logger.error(f"GitHub Pages状態取得エラー: {e}")
            return jsonify({'status': 'error', 'message': str(e)}), 500

    # ========== 担当者名変換API ==========

    @app.route('/api/salesman-aliases', methods=['GET'])
    def get_salesman_aliases():
        """担当者名変換マッピング一覧を取得"""
        try:
            from database import get_salesman_aliases as db_get_aliases
            aliases = db_get_aliases()
            return jsonify({
                'status': 'success',
                'aliases': aliases
            })
        except Exception as e:
            logger.error(f"担当者名変換マッピング取得エラー: {e}")
            return jsonify({'status': 'error', 'message': str(e)}), 500

    @app.route('/api/salesman-aliases', methods=['POST'])
    def add_salesman_alias():
        """担当者名変換マッピングを追加（既存データも自動変換）"""
        try:
            from database import add_salesman_alias as db_add_alias
            data = request.get_json()
            from_name = data.get('from_name', '').strip()
            to_name = data.get('to_name', '').strip()

            if not from_name or not to_name:
                return jsonify({
                    'status': 'error',
                    'message': '変換元と変換先の担当者名を入力してください'
                }), 400

            if from_name == to_name:
                return jsonify({
                    'status': 'error',
                    'message': '変換元と変換先が同じです'
                }), 400

            result = db_add_alias(from_name, to_name)

            if result['success']:
                return jsonify({
                    'status': 'success',
                    'message': result['message'],
                    'migrated_count': result['migrated_count']
                })
            else:
                return jsonify({
                    'status': 'error',
                    'message': result['message']
                }), 400

        except Exception as e:
            logger.error(f"担当者名変換マッピング追加エラー: {e}")
            return jsonify({'status': 'error', 'message': str(e)}), 500

    @app.route('/api/salesman-aliases/<int:alias_id>', methods=['DELETE'])
    def delete_salesman_alias(alias_id):
        """担当者名変換マッピングを削除"""
        try:
            from database import delete_salesman_alias as db_delete_alias
            result = db_delete_alias(alias_id)

            if result['success']:
                return jsonify({
                    'status': 'success',
                    'message': result['message']
                })
            else:
                return jsonify({
                    'status': 'error',
                    'message': result['message']
                }), 400

        except Exception as e:
            logger.error(f"担当者名変換マッピング削除エラー: {e}")
            return jsonify({'status': 'error', 'message': str(e)}), 500

    # ========== データ確認API ==========

    @app.route('/api/data/tables', methods=['GET'])
    def get_tables():
        """利用可能なテーブル一覧を取得"""
        tables = [
            {'id': 'monthly_summary', 'name': '月別サマリー', 'description': '月ごとの売上概要'},
            {'id': 'school_sales', 'name': '学校別売上', 'description': '学校ごとの月別売上'},
            {'id': 'event_sales', 'name': 'イベント別売上', 'description': 'イベントごとの月別売上'},
            {'id': 'member_rates', 'name': '会員率', 'description': '学校・学年ごとの会員率'}
        ]
        return jsonify({'status': 'success', 'tables': tables})

    @app.route('/api/data/filters', methods=['GET'])
    def get_filter_options():
        """フィルター選択肢を取得"""
        try:
            from database import get_connection
            conn = get_connection()
            cursor = conn.cursor()

            # 年度一覧
            cursor.execute('SELECT DISTINCT fiscal_year FROM monthly_summary ORDER BY fiscal_year DESC')
            fiscal_years = [row[0] for row in cursor.fetchall()]

            # 事業所一覧
            cursor.execute('SELECT DISTINCT region FROM schools WHERE region IS NOT NULL AND region != "" ORDER BY region')
            regions = [row[0] for row in cursor.fetchall()]

            # 担当者一覧
            cursor.execute('SELECT DISTINCT manager FROM schools WHERE manager IS NOT NULL AND manager != "" ORDER BY manager')
            managers = [row[0] for row in cursor.fetchall()]

            # 学校一覧
            cursor.execute('SELECT id, school_name FROM schools ORDER BY school_name')
            schools = [{'id': row[0], 'name': row[1]} for row in cursor.fetchall()]

            conn.close()

            return jsonify({
                'status': 'success',
                'filters': {
                    'fiscal_years': fiscal_years,
                    'months': list(range(1, 13)),
                    'regions': regions,
                    'managers': managers,
                    'schools': schools
                }
            })

        except Exception as e:
            logger.error(f"フィルター選択肢取得エラー: {e}")
            return jsonify({'status': 'error', 'message': str(e)}), 500

    @app.route('/api/data/search', methods=['POST'])
    def search_data():
        """データ検索"""
        try:
            from database import get_connection
            data = request.get_json()
            table = data.get('table', 'monthly_summary')
            filters = data.get('filters', {})
            limit = data.get('limit', 100)
            offset = data.get('offset', 0)

            conn = get_connection()
            cursor = conn.cursor()

            # テーブルごとにクエリを構築
            if table == 'monthly_summary':
                query, params = _build_monthly_summary_query(filters)
            elif table == 'school_sales':
                query, params = _build_school_sales_query(filters)
            elif table == 'event_sales':
                query, params = _build_event_sales_query(filters)
            elif table == 'member_rates':
                query, params = _build_member_rates_query(filters)
            else:
                return jsonify({'status': 'error', 'message': '無効なテーブル名'}), 400

            # 件数取得
            count_query = f"SELECT COUNT(*) FROM ({query})"
            cursor.execute(count_query, params)
            total_count = cursor.fetchone()[0]

            # データ取得（ページング）
            data_query = f"{query} LIMIT ? OFFSET ?"
            cursor.execute(data_query, params + [limit, offset])
            columns = [description[0] for description in cursor.description]
            rows = [dict(zip(columns, row)) for row in cursor.fetchall()]

            conn.close()

            return jsonify({
                'status': 'success',
                'data': rows,
                'columns': columns,
                'total_count': total_count,
                'limit': limit,
                'offset': offset
            })

        except Exception as e:
            logger.error(f"データ検索エラー: {e}")
            return jsonify({'status': 'error', 'message': str(e)}), 500

    @app.route('/api/data/export', methods=['POST'])
    def export_data():
        """データCSVエクスポート"""
        try:
            import csv
            import io
            from database import get_connection

            data = request.get_json()
            table = data.get('table', 'monthly_summary')
            filters = data.get('filters', {})

            conn = get_connection()
            cursor = conn.cursor()

            # テーブルごとにクエリを構築
            if table == 'monthly_summary':
                query, params = _build_monthly_summary_query(filters)
            elif table == 'school_sales':
                query, params = _build_school_sales_query(filters)
            elif table == 'event_sales':
                query, params = _build_event_sales_query(filters)
            elif table == 'member_rates':
                query, params = _build_member_rates_query(filters)
            else:
                return jsonify({'status': 'error', 'message': '無効なテーブル名'}), 400

            cursor.execute(query, params)
            columns = [description[0] for description in cursor.description]
            rows = cursor.fetchall()

            conn.close()

            # CSV生成
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(columns)
            writer.writerows(rows)

            csv_content = output.getvalue()
            output.close()

            # BOMつきUTF-8でレスポンス
            response = Response(
                '\ufeff' + csv_content,
                mimetype='text/csv; charset=utf-8',
                headers={
                    'Content-Disposition': f'attachment; filename=export_{table}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
                }
            )

            return response

        except Exception as e:
            logger.error(f"CSVエクスポートエラー: {e}")
            return jsonify({'status': 'error', 'message': str(e)}), 500

    def _build_monthly_summary_query(filters):
        """月別サマリークエリ構築"""
        query = '''
            SELECT
                ms.fiscal_year AS 年度,
                ms.month AS 月,
                ms.total_sales AS 総売上,
                ms.direct_sales AS 直取引売上,
                ms.studio_school_sales AS 写真館学校売上,
                ms.school_count AS 学校数,
                ms.budget AS 予算,
                ms.budget_rate AS 予算比,
                ms.yoy_rate AS 昨年比
            FROM monthly_summary ms
            WHERE 1=1
        '''
        params = []

        if filters.get('fiscal_year'):
            query += ' AND ms.fiscal_year = ?'
            params.append(filters['fiscal_year'])
        if filters.get('month'):
            query += ' AND ms.month = ?'
            params.append(filters['month'])

        query += ' ORDER BY ms.fiscal_year DESC, ms.month DESC'
        return query, params

    def _build_school_sales_query(filters):
        """学校別売上クエリ構築"""
        query = '''
            SELECT
                ss.fiscal_year AS 年度,
                ss.month AS 月,
                s.school_name AS 学校名,
                s.attribute AS 属性,
                s.region AS 事業所,
                s.manager AS 担当者,
                s.studio_name AS 写真館,
                ss.sales AS 売上
            FROM school_sales ss
            JOIN schools s ON ss.school_id = s.id
            WHERE 1=1
        '''
        params = []

        if filters.get('fiscal_year'):
            query += ' AND ss.fiscal_year = ?'
            params.append(filters['fiscal_year'])
        if filters.get('month'):
            query += ' AND ss.month = ?'
            params.append(filters['month'])
        if filters.get('region'):
            query += ' AND s.region = ?'
            params.append(filters['region'])
        if filters.get('manager'):
            query += ' AND s.manager = ?'
            params.append(filters['manager'])
        if filters.get('school_name'):
            query += ' AND s.school_name LIKE ?'
            params.append(f'%{filters["school_name"]}%')

        query += ' ORDER BY ss.fiscal_year DESC, ss.month DESC, ss.sales DESC'
        return query, params

    def _build_event_sales_query(filters):
        """イベント別売上クエリ構築"""
        query = '''
            SELECT
                es.fiscal_year AS 年度,
                es.month AS 月,
                s.school_name AS 学校名,
                e.event_name AS イベント名,
                e.start_date AS 開始日,
                s.region AS 事業所,
                s.manager AS 担当者,
                es.sales AS 売上
            FROM event_sales es
            JOIN events e ON es.event_id = e.id
            JOIN schools s ON e.school_id = s.id
            WHERE 1=1
        '''
        params = []

        if filters.get('fiscal_year'):
            query += ' AND es.fiscal_year = ?'
            params.append(filters['fiscal_year'])
        if filters.get('month'):
            query += ' AND es.month = ?'
            params.append(filters['month'])
        if filters.get('region'):
            query += ' AND s.region = ?'
            params.append(filters['region'])
        if filters.get('manager'):
            query += ' AND s.manager = ?'
            params.append(filters['manager'])
        if filters.get('school_name'):
            query += ' AND s.school_name LIKE ?'
            params.append(f'%{filters["school_name"]}%')
        if filters.get('event_start_date'):
            query += ' AND e.start_date = ?'
            params.append(filters['event_start_date'])

        query += ' ORDER BY es.fiscal_year DESC, es.month DESC, es.sales DESC'
        return query, params

    def _build_member_rates_query(filters):
        """会員率クエリ構築"""
        query = '''
            SELECT
                mr.fiscal_year AS 年度,
                mr.snapshot_date AS スナップショット日,
                s.school_name AS 学校名,
                s.attribute AS 属性,
                s.region AS 事業所,
                s.manager AS 担当者,
                mr.grade_category AS 学年カテゴリ,
                mr.grade_name AS 学年名,
                mr.student_count AS 生徒数,
                mr.member_count AS 会員数,
                mr.member_rate AS 会員率
            FROM member_rates mr
            JOIN schools s ON mr.school_id = s.id
            WHERE 1=1
        '''
        params = []

        if filters.get('fiscal_year'):
            query += ' AND mr.fiscal_year = ?'
            params.append(filters['fiscal_year'])
        if filters.get('region'):
            query += ' AND s.region = ?'
            params.append(filters['region'])
        if filters.get('manager'):
            query += ' AND s.manager = ?'
            params.append(filters['manager'])
        if filters.get('school_name'):
            query += ' AND s.school_name LIKE ?'
            params.append(f'%{filters["school_name"]}%')

        query += ' ORDER BY mr.fiscal_year DESC, mr.snapshot_date DESC, s.school_name'
        return query, params

    # フロントエンド配信（ビルド済みの場合）
    @app.route('/')
    def serve_index():
        """フロントエンドのindex.htmlを配信"""
        dist_dir = FRONTEND_DIR / 'dist'
        if dist_dir.exists():
            return send_from_directory(str(dist_dir), 'index.html')
        else:
            # 開発用: srcディレクトリのindex.htmlを配信
            return send_from_directory(str(FRONTEND_DIR), 'index.html')

    @app.route('/<path:path>')
    def serve_static(path):
        """静的ファイルを配信"""
        # APIルートはここで処理しない（404を返す）
        if path.startswith('api/'):
            return jsonify({'status': 'error', 'message': 'Not found'}), 404

        dist_dir = FRONTEND_DIR / 'dist'
        if dist_dir.exists():
            file_path = dist_dir / path
            if file_path.exists():
                return send_from_directory(str(dist_dir), path)
        # フォールバック: index.htmlを返す（SPA対応）
        return serve_index()

    return app
