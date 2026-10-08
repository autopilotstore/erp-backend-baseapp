"""Master hashtag produk — dirujuk oleh child table `Item Hashtag` dan
`Dynamic Product Bundle Hashtag`.

`name` = hashtag itu sendiri (autoname `field:hashtag`, pola sama seperti doctype
`Brand`), ditulis huruf kecil tanpa tanda '#'.

Tidak ada validasi di sini: aturan penulisan hashtag ditegakkan oleh hook Item
(`baseapp.utils.normalize_item_hashtags`), yang membersihkan input, menolak hashtag yang
belum terdaftar, dan menghapus baris duplikat/kosong.
"""

from frappe.model.document import Document


class Hashtag(Document):
	pass
