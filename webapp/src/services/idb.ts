import { openDB } from 'idb';
import type { DBSchema } from 'idb';

interface IKNOSDB extends DBSchema {
  cases: {
    key: string;
    value: any;
  };
  geometries: {
    key: string;
    value: any;
  };
}

export const initDB = async () => {
  return openDB<IKNOSDB>('iknos-db', 1, {
    upgrade(db) {
      if (!db.objectStoreNames.contains('cases')) {
        db.createObjectStore('cases');
      }
      if (!db.objectStoreNames.contains('geometries')) {
        db.createObjectStore('geometries');
      }
    },
  });
};
