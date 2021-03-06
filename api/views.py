import json
import requests
from datetime import datetime

from flask import request, abort, Blueprint
from sqlalchemy.orm.exc import NoResultFound

from api.feed import Feed
from logger import log

api_blueprint = Blueprint('api_blueprint', __name__, template_folder='')


default_feeds = [
    'http://feeds.reuters.com/Reuters/worldNews',
    'http://hosted2.ap.org/atom/APDEFAULT/cae69a7523db45408eeb2b3a98c0c9c5',
    'http://feeds.bbci.co.uk/news/world/rss.xml',
    'http://feeds.bbci.co.uk/news/world/africa/rss.xml',
    'http://feeds.bbci.co.uk/news/world/asia/rss.xml',
    'http://feeds.bbci.co.uk/news/world/europe/rss.xml',
    'http://feeds.bbci.co.uk/news/world/latin_america/rss.xml',
    'http://feeds.bbci.co.uk/news/world/middle_east/rss.xml',
    'http://feeds.bbci.co.uk/news/world/us_and_canada/rss.xml',
    'http://feeds.bbci.co.uk/news/england/rss.xml',
    'http://feeds.bbci.co.uk/news/northern_ireland/rss.xml',
    'http://feeds.bbci.co.uk/news/scotland/rss.xml',
    'http://feeds.bbci.co.uk/news/wales/rss.xml',
    'http://feeds.foxnews.com/foxnews/world',
    'http://www.npr.org/rss/rss.php?id=1004',
    'http://www.usnews.com/rss/news',
    'http://rss.cnn.com/rss/cnn_world.rss',
    'http://rss.nytimes.com/services/xml/rss/nyt/MiddleEast.xml',
    'http://rss.nytimes.com/services/xml/rss/nyt/Europe.xml',
    'http://rss.nytimes.com/services/xml/rss/nyt/AsiaPacific.xml',
    'http://rss.nytimes.com/services/xml/rss/nyt/Africa.xml',
    'http://rss.nytimes.com/services/xml/rss/nyt/Americas.xml',
    'http://rssfeeds.usatoday.com/usatodaycomworld-topstories&x=1',
    'http://feeds.abcnews.com/abcnews/internationalheadlines',
    'http://feeds.skynews.com/feeds/rss/world.xml',
    'http://globalnews.ca/world/feed/',
    'http://www.cbc.ca/cmlink/rss-world',
    'http://www.telegraph.co.uk/news/worldnews/rss',
    'http://www.aljazeera.com/xml/rss/all.xml'
]


@api_blueprint.route('/clear', methods=['GET'])
def clear():
    from api.kv_store import Base, engine
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    return json.dumps({}), 200


@api_blueprint.route('/store', methods=['GET'])
def store():
    from api.kv_store import KvStore, session

    now = datetime.now()
    key = "feeds_{}_{}".format(now.strftime('%Y-%m-%d'), now.month / 6)

    existing = session.query(KvStore.id).filter(KvStore.key == key).count()
    if existing == 0:
        log.info("Staring cache of {}...".format(key))
        feeds = {}

        for url in default_feeds:
            r = requests.get(url)
            feeds[url] = r.text
            if r.status_code != 200:
                log.error("HTTP error code {} for {}".format(
                    r.status_code, url))

        new_store = KvStore(key, feeds)
        session.add(new_store)
        session.commit()
        log.info("Feed Data saved to db with key {}".format(key))
    else:
        feeds = session.query(KvStore).filter(KvStore.key == key).one().value

    key_x = key + '_x'
    existing = session.query(KvStore.id).filter(KvStore.key == key_x).count()

    if existing == 0:
        log.info("Extracting feed data...")
        feeds_x = {}
        for url in default_feeds:
            data = feeds[url]
            feed = Feed(feed=data)
            feed.extract()

            feeds_x[url] = json.dumps(feed.serializable())

        new_store_x = KvStore(key_x, feeds_x)
        session.add(new_store_x)
        session.commit()
        log.info("Processed data saved to db with key {}".format(key))

    return json.dumps({'data': key, 'processed': key_x}), 200


@api_blueprint.route('/feeds', methods=['POST'])
def feeds():
    from api.kv_store import KvStore, session

    url = request.form.get('url')

    cached = session.query(KvStore).filter(
        KvStore.key.like("%_x")).order_by(KvStore.id.desc()).first()

    return cached.value[url], 200
    abort(400)
