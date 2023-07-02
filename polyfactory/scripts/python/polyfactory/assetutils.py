from husd import assetutils as hassetutils


class AssetGallery(hassetutils.AssetGallery):

    @staticmethod
    def addTags(asset, *tags):

        datasource = AssetGallery.getDataSource_()
        assetId = next(id for id in datasource.getItemIds() if datasource.label(id) == asset)
        for tag in tags:
            datasource.addTag(assetId, tag)
