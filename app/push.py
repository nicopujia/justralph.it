import json
import sqlite3

from pywebpush import WebPushException, webpush


def send_push_notification(slug, message, db_path, vapid_private_key_path, vapid_claims_email):
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT id, subscription_json FROM push_subscriptions WHERE project_slug = ?",
            (slug,),
        ).fetchall()
        for row in rows:
            try:
                subscription_info = json.loads(row["subscription_json"])
                webpush(
                    subscription_info=subscription_info,
                    data=message,
                    vapid_private_key=vapid_private_key_path,
                    vapid_claims={"sub": vapid_claims_email},
                )
            except WebPushException as e:
                if hasattr(e, "response") and e.response is not None and e.response.status_code == 410:
                    conn.execute("DELETE FROM push_subscriptions WHERE id = ?", (row["id"],))
                    conn.commit()
            except Exception:
                pass
        conn.close()
    except Exception:
        pass
