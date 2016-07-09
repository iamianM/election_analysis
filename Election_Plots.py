import pandas as pd
import numpy as np
from datetime import date
import matplotlib.pyplot as plt
from PIL import Image
from NMF_Clustering import NMFClustering
from wordcloud import WordCloud, ImageColorGenerator
from scipy.misc import imread
from scrapers.load_data import get_topic_labels
plt.style.use('ggplot')


class ElectionPlotting(object):

    def __init__(self, df, nmf=None, num_topics=None, figsize=(14,8)):
        ''' init docstring
        INPUT:
            df:
            nmf:
            num_topics:
        Explain how it works if you don't pass an nmf object
        '''
        self.df = df
        if isinstance(nmf, NMFClustering):
            # Check to make sure that the object has been fit to the data
            if not hasattr(nmf, 'W_matrix'):
                nmf.fit(df)
            self.nmf = nmf
        elif num_topics:
            self.nmf = NMFClustering(num_topics)
            self.nmf.fit(df)
        else:
            raise ValueError("You must either supply a NMFClustering object or specify the number of topics!")
        self.labels = get_topic_labels()
        self.outlet_sizes = [len(df.loc[df['source'] == outlet]) for outlet in zip(*self.nmf.outlets)[0]]
        self.frequency = {'D': 'Daily', 'W': 'Weekly', 'M': 'Monthly'}
        self.figsize = figsize


    def article_count_by_time(self, searchterm=None, topic_num=None, source=False, freq='W', normalize=False, marker='o', year=False, fig=None, label=None, legend_label=None):
        if isinstance(fig, tuple):
            fig = self._create_fig(fig)
        elif not fig:
            fig = self._create_fig()

        # If a specific topic was given set the label and subset the dataframe
        if topic_num:
            label = self.labels.get(topic_num, 'Unknown')
            df = self.df.loc[self.nmf.labels[:, topic_num]]
        else:
            df = self.df

        # Subset the dataframe if a searchterm is provided
        if searchterm:
            df = df.loc[df['lemmatized_text'].str.contains(searchterm)]

        # If source is set, split up into a line for each news source
        if source:
            timeseries = [pd.Series([1], index=df.loc[df['source'] == outlet, 'date_published']).resample(freq).sum().fillna(0) for outlet in zip(*self.nmf.outlets)[0]]
            if normalize:
                timeseries = [ts / outlet_size for ts, outlet_size in zip(timeseries, self.outlet_sizes)]
                plt.ylabel('Article Frequency (freq = {})'.format(freq), fontsize=12)
            else:
                plt.ylabel('Article Count (Freq = {})'.format(freq), fontsize=12)

            # plt.subplots_adjust(left=0.08, bottom=0.12, right=0.95, top=0.92)

            for idx, ts in enumerate(timeseries):
                if len(ts):
                    ts.plot(marker=marker, label=self.nmf.outlets[idx][1], c=self.nmf.outlets[idx][2])
            plt.xlabel('Date Published ({})'.format(self.frequency[freq]), fontsize=12)
            plt.legend(loc='best')
        else:
            ts = pd.Series([1], index=df['date_published']).resample(freq).sum().fillna(0)
            if legend_label:
                ts.plot(marker=marker, label=label)
            else:
                ts.plot(marker=marker)
            plt.xlabel('Date Published ({})'.format(self.frequency[freq]), fontsize=12)
            plt.ylabel('Article Count (freq={})'.format(freq), fontsize=12)
        if label:
            plt.title('Topic Number {}: {}'.format(topic_num, label))
        if searchterm:
            plt.title("Articles Containing '{}'".format(searchterm), fontsize=14)
        plt.subplots_adjust(left=0.06, bottom=0.1, right=0.97, top=0.92)

        # Adjust the date range for the x-axis to allow for two weeks on either side.  If year is set to True, show from the beginning to the end of the minimum and maximum years respectively
        if year == True:
            xmin = df['date_published'].min()
            xmin = pd.to_datetime('{}-01-01'.format(xmin.year)) - pd.Timedelta(weeks=2)
            xmax = df['date_published'].max()
            xmax = pd.to_datetime('{}-01-01'.format(xmax.year+1)) + pd.Timedelta(weeks=2)
            plt.xlim((xmin, xmax))
        elif year == False:
            xmin = df['date_published'].min() - pd.Timedelta(weeks=2)
            xmax = df['date_published'].max() + pd.Timedelta(weeks=2)
            plt.xlim((xmin, xmax))



    def _create_fig(self, figsize=None, watermark=True):
        if figsize == None:
            figsize = self.figsize

        fig = plt.figure(figsize=figsize)

        if watermark:
            fig.text(0.05, 0.03, 'Author: Erich Wellinger', fontsize=10, alpha=0.7)
            fig.text(0.33, 0.75, 'github.com/ewellinger/election_analysis', fontsize=20, color='gray', alpha=0.5)
        return fig


    def candidate_plots(self, candidate_topic_idxs, title, byline=None, freq='W', fig=None):
        ''' candidate_plots plots multiple topics on one plot
        candidate_topic_idxs: list of int
            Should be a list of int specifying which topic_num to plot
        title: str
            Title for the plot
        byline: str
            Byline to go beneath the title
        '''
        if isinstance(fig, tuple):
            fig = self._create_fig(fig)
        elif not fig:
            fig = self._create_fig()

        for candidate in candidate_topic_idxs:
            self.article_count_by_time(topic_num=candidate, freq=freq, legend_label=self.labels.get(candidate, 'Unknown'), fig=fig, year=None)

        # Make sure the xlims have a buffer on either side of earliest and latest values
        xmin, xmax = plt.xlim()
        # Add in a buffer to either and reset the xlims
        xmin = pd.to_datetime(xmin*7, unit='D') - pd.Timedelta(weeks=2)
        xmax = pd.to_datetime(xmax*7, unit='D') + pd.Timedelta(weeks=2)
        plt.xlim((xmin, xmax))

        plt.legend(loc='best')
        plt.subplots_adjust(left=0.05, bottom=0.1, right=0.97)
        plt.suptitle(title)
        if byline:
            plt.title(byline, fontsize=10)


    def topic_word_cloud(self, topic_num, max_words=300, figsize=None, width=2400, height=1300, ax=None, mask_fname=None, inherit_color=False):
        ''' Create word cloud for a given topic
        INPUT:
            topic_idx: int
            max_words: int
                Max number of words to encorporate into the word cloud
            figsize: tuple (int, int)
                Size of the figure if an axis isn't passed
            width: int
            height: int
            ax: None or matplotlib axis object
            mask_fname: None or str
                None if no mask is desired, otherwise a string providing the path the image being used as the mask
            inherit_color: bool, default False
                Indicates whether the wordcloud should inherit the colors from the image mask
        '''
        if figsize == None:
            figsize = self.figsize

        if mask_fname:
            mask = np.array(Image.open(mask_fname))
            wc = WordCloud(background_color='white', max_words=max_words, mask=mask, width=width, height=height)
        else:
            wc = WordCloud(background_color='white', max_words=max_words, width=width, height=height)
        word_freq = self.nmf.topic_word_frequency(topic_num)

        # Fit the WordCloud object to the specific topic's word frequencies
        wc.fit_words(word_freq)

        # Create the matplotlib figure and axis if they weren't passed in
        if not ax:
            fig = plt.figure(figsize=self.figsize)
            ax = fig.add_subplot(111)

        if mask_fname and inherit_color:
            image_colors = ImageColorGenerator(imread(mask_fname))
            plt.imshow(wc.recolor(color_func=image_colors))
            plt.axis('off')
        else:
            ax.imshow(wc)
            ax.axis('off')


    def normalized_source_barchart(self, topic_num, ax=None):
        ''' Make a bar chart relecting the normalized reporting by source
        INPUT:
            topic_num: int
        '''
        num_articles = self.nmf.labels[:, topic_num].sum()
        df = self.df.loc[self.nmf.labels[:, topic_num]]
        percent_by_source = [float(len(df.loc[df['source'] == outlet])) / num_articles for outlet in zip(*self.nmf.outlets)[0]]
        normalized = [percent / outlet_size for percent, outlet_size in zip(percent_by_source, self.outlet_sizes)]
        normalized = [percent / np.sum(normalized) for percent in normalized]

        if not ax:
            fig, ax = plt.subplots(1, figsize=(2.5, 5))

        for idx, percent in enumerate(normalized):
            ax.bar(0, percent, width=1, label=self.nmf.outlets[idx][1], color=self.nmf.outlets[idx][2], bottom=np.sum(normalized[:idx]))
            if percent >= 0.1:
                ax.text(0.5, np.sum(normalized[:idx]) + 0.5*percent, '{0}: {1:.1f}%'.format(self.nmf.outlets[idx][1], 100*percent), horizontalalignment='center', verticalalignment='center')
            elif percent >= 0.05:
                ax.text(0.5, np.sum(normalized[:idx]) + 0.5*percent, '{0}: {1:.1f}%'.format(self.nmf.outlets[idx][1], 100*percent), horizontalalignment='center', verticalalignment='center', fontsize=10)
            elif percent >= 0.025:
                ax.text(0.5, np.sum(normalized[:idx]) + 0.5*percent, '{0}: {1:.1f}%'.format(self.nmf.outlets[idx][1], 100*percent), horizontalalignment='center', verticalalignment='center', fontsize=8)

        plt.axis('off')
        plt.title('% Reported By Source (Normalized)', fontsize=10)


    def topic_time_and_cloud(self, topic_num, source=False, year=False, title=None):
        ''' Creates viz of topic including counts over time, word cloud, and breakdown by source
        INPUT:
            topic_num: int
                Which topic to generate the plot for
            source: bool (default False)
                Arg passed to the article_count_by_time function
            year: bool (default False)
                Arg passed to the article_count_by_time function
            title: str (default None)
                str to use as title, otherwise "Topic Number {topic_num}: {label}" will be used
        OUTPUT:
            ax1: Matplotlib axis object
                Used to modify the article count by time axis (e.g. add vertical lines to signify event of import)
        '''
        fig = self._create_fig(figsize=(14, 8.5), watermark=False)

        ax1 = fig.add_axes([0.05, 0.5, 0.93, 0.41])
        self.article_count_by_time(topic_num=topic_num, source=source, year=year, fig=fig)
        ax1.xaxis.labelpad = -4
        plt.title('Number of Articles in Topic: {}'.format(self.nmf.labels[:, topic_num].sum()), x=0.4825)
        if title == None:
            plt.suptitle('Topic Number {}: {}'.format(topic_num, self.labels.get(topic_num, "Unknown")), fontsize=20)
        else:
            plt.suptitle(title, fontsize=20)

        fig.text(0.05, 0.44, 'Author: Erich Wellinger', fontsize=10, alpha=0.7)
        fig.text(0.33, 0.8, 'github.com/ewellinger/election_analysis', fontsize=20, color='gray', alpha=0.5)

        ax2 = fig.add_axes([0.025, 0, 0.79, 0.43])
        self.topic_word_cloud(topic_num, ax=ax2, width=1900, height=625)

        ax3 = fig.add_axes([0.825, 0.01, 0.15555, 0.4])
        self.normalized_source_barchart(topic_num, ax=ax3)

        return ax1


if __name__=='__main__':
    df = pd.read_pickle('election_data.pkl')

    nmf = NMFClustering(250)
    nmf.fit(df)

    ep = ElectionPlotting(df, nmf)

    # Plot a general plot of all the articles over time
    # ep.article_count_by_time()
    # plt.show()

    # Plot all the articles split up by source over time
    # ep.article_count_by_time(source=True)
    # plt.show()

    # Create an overall visualization of an entire topic
    # ep.topic_time_and_cloud(9)
    # plt.show()
