import argparse
import sys
from . import db as store
from .index import index_paths, regeocode
from .paths import DB_PATH
from . import __version__


def main(argv=None):
    p = argparse.ArgumentParser(
        prog="meridian",
        description="Point it at a corpus. Cut it on concept, place, and time.",
    )
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="cmd", required=True)

    idx = sub.add_parser("index", help="Extract and store files")
    idx.add_argument("paths", nargs="+", help="Files or directories")
    idx.add_argument("--no-geo", action="store_true", help="Skip gazetteer lookups")

    srv = sub.add_parser("serve", help="API + Vue UI")
    srv.add_argument("--host", default="127.0.0.1")
    srv.add_argument("--port", type=int, default=8090)

    rst = sub.add_parser("reset", help="Empty the catalog; corpus stays")
    rst.add_argument("--yes", action="store_true")

    geo_p = sub.add_parser("geocode", help="Re-resolve places from stored text")
    geo_p.add_argument("--no-geo", action="store_true", help="NER only; no gazetteer")

    sub.add_parser("gazetteer", help="Download and build the local GeoNames gazetteer")

    args = p.parse_args(argv)
    if args.cmd == "index":
        index_paths(args.paths, resolve_geo=not args.no_geo)
    elif args.cmd == "serve":
        from .serve import run
        print(f"Meridian on http://{args.host}:{args.port}/")
        print(f"catalog {DB_PATH}")
        try:
            run(host=args.host, port=args.port)
        except KeyboardInterrupt:
            print("stopped")
    elif args.cmd == "reset":
        if not args.yes:
            ans = input("Empty the Meridian catalog? [y/N] ").strip().lower()
            if ans not in ("y", "yes"):
                print("aborted")
                return 1
        store.reset()
        print(f"reset {DB_PATH}")
    elif args.cmd == "geocode":
        regeocode(resolve_geo=not args.no_geo)
    elif args.cmd == "gazetteer":
        from . import geonames
        geonames.build()
    return 0


if __name__ == "__main__":
    sys.exit(main())
