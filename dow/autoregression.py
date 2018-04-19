import pandas as pd
import numpy as np
from statsmodels.tsa.ar_model import AR
from sklearn.metrics import mean_squared_error
import matplotlib.pyplot as plt

#Import data
intc = pd.read_csv('INTC.csv')

#Extract target
close = intc['Close'].values

#Separate train/test
train, test = close[:2500], close[2500:]

#Train model
model = AR(train)
model_fit = model.fit()
print('Lag: %s' % model_fit.k_ar)
print('Coefficients: %s' % model_fit.params)
# make predictions
predictions = model_fit.predict(start=len(train), end=len(train)+len(test)-1, dynamic=False)
#Calculate root mean squared error
error = (mean_squared_error(test, predictions))**.5

fig, ax = plt.subplots(figsize = (15,15))
ax.plot(test, label = "Actual close price")
ax.plot(predictions, color='red', label = "Predicted close price")
plt.title('Basic Autoregressor')
plt.legend()
plt.show()
